/**
 * ``AskApprovalCache`` —— ask 路径的 session-scoped 短期通行池（D-9.1b 修订）。
 *
 * 解决"第一次 ask 后用户在 chat 里说'允许'，第二次重调还是被拦"的死循环：
 *
 * 1. 第一次 ``permissionResolver=ask`` 命中 → with-hooks 返 ``requiresApproval`` 错误
 *    + 调 ``mark(sessionId, toolName, input)`` 记一笔
 * 2. Agent 在 chat 里向用户说明 + 等用户口头同意
 * 3. 用户回 "允许 / 同意" → agent 重调同一个 tool 同一份 input
 * 4. 第二次 ask 命中 → with-hooks 先调 ``consume(sessionId, toolName, input)`` ——
 *    若命中（同 session 60s 内有 mark）→ 一次性消费 + 放行；未命中 → 走第 1 步
 *
 * 安全模型（接受性的设计取舍）：
 *
 * - sessionId 是 *agent loop 范围内*（Mastra thread / run id），不跨会话；A 用户
 *   的允许不会被 B 用户复用
 * - 60s TTL：足够给 agent 在 chat 转一圈，短到防 agent 长期"残留许可"复用
 * - 一次性：消费即删；agent 想再做同样动作必须再走一轮 ask
 * - **强制跨 user turn**：entry 记录首次 ask 的 ``ctx.runId``，只有后续不同
 *   ``runId`` 才能消费。同一模型 turn 内立即重试只会再次得到审批要求，不能自批。
 * - 缺少 turn ID 时 fail closed：可记录待审批项，但不能消费。
 */

interface AskCacheEntry {
  markedAt: number;
  /** 首次触发 ask 的 user-turn ID；消费时必须来自另一个 turn。 */
  turnId: string | undefined;
  /** TTL 到期自动清理的 timer，consume 时记得 clearTimeout */
  timer: ReturnType<typeof setTimeout>;
}

export type AskConsumeResult =
  | "consumed"
  | "miss"
  | "same_turn"
  | "missing_turn_id";

const DEFAULT_TTL_MS = 60_000;

/**
 * Telemetry sink —— 默认 ``console.log(JSON.stringify(record))``，与 ``audit-log.ts``
 * 同款 stdout-friendly 格式。测试可注入自定义 sink。
 */
export type AskCacheTelemetrySink = (record: Record<string, unknown>) => void;

const defaultTelemetrySink: AskCacheTelemetrySink = (r) => {
  console.log(JSON.stringify(r));
};

/**
 * **稳定** JSON stringify —— object keys 按字典序，避免 ``{a,b}`` vs ``{b,a}`` 撞不上。
 *
 * 必须用 stable 形式：DeepSeek / GPT 生成 tool call JSON 时 key 顺序在两次调用之间
 * 经常变（实测 ``{candidateId, reason}`` ↔ ``{reason, candidateId}``），plain
 * ``JSON.stringify`` 会给两个不同字符串 → cache miss → 死循环。
 */
function stableStringify(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`).join(",")}}`;
}

export class AskApprovalCache {
  private readonly entries = new Map<string, AskCacheEntry>();
  private readonly ttlMs: number;
  private readonly telemetry: AskCacheTelemetrySink;
  /** 记录已打过 __global__ fallback warning，避免每次 mark/consume 都刷屏。 */
  private warnedGlobalFallback = false;

  constructor(ttlMs: number = DEFAULT_TTL_MS, telemetry?: AskCacheTelemetrySink) {
    if (ttlMs <= 0) throw new Error(`ttlMs must be positive, got ${ttlMs}`);
    this.ttlMs = ttlMs;
    this.telemetry = telemetry ?? defaultTelemetrySink;
  }

  /** 拼 cache key。无 sessionId 时回退到 ``"__global__"`` —— 单进程 dev 环境够用。 */
  private static keyFor(
    sessionId: string | undefined,
    toolName: string,
    input: unknown,
  ): string {
    const sid = sessionId && sessionId.length > 0 ? sessionId : "__global__";
    return `${sid}::${toolName}::${stableStringify(input)}`;
  }

  /** 进程内仅 warn 一次 sessionId 缺失：多用户场景下不同用户的 ask 会撞同一个 __global__ entry。 */
  private maybeWarnGlobalFallback(
    sessionId: string | undefined,
    op: string,
    toolName: string,
  ): void {
    if (this.warnedGlobalFallback) return;
    if (sessionId && sessionId.length > 0) return;
    this.warnedGlobalFallback = true;
    console.warn(
      `[ask-cache] sessionId missing for ${op}("${toolName}"); falling back to "__global__". ` +
        "Multi-user safety degraded. Check defaultGetSessionId in with-hooks.ts.",
    );
  }

  /**
   * 标记 (sessionId, toolName, input) 已被 ask 过，并记录当前 user turn。
   * 若已存在条目，重置 TTL，但同 turn 重试仍不能消费。
   */
  mark(
    sessionId: string | undefined,
    toolName: string,
    input: unknown,
    turnId: string | undefined,
  ): void {
    this.maybeWarnGlobalFallback(sessionId, "mark", toolName);
    const key = AskApprovalCache.keyFor(sessionId, toolName, input);
    const existing = this.entries.get(key);
    if (existing) clearTimeout(existing.timer);
    const timer = setTimeout(() => {
      this.entries.delete(key);
      this.telemetry({
        event: "ask_cache_expired",
        toolName,
        sessionId: sessionId ?? null,
        ttlMs: this.ttlMs,
        ts: new Date().toISOString(),
      });
    }, this.ttlMs);
    this.entries.set(key, { markedAt: Date.now(), turnId, timer });
    this.telemetry({
      event: "ask_marked",
      toolName,
      sessionId: sessionId ?? null,
      hasTurnId: turnId !== undefined,
      ts: new Date().toISOString(),
    });
  }

  /**
   * 检查 + 一次性消费。只有 key 命中、TTL 有效且当前 ``turnId`` 与标记时不同，
   * 才返回 ``consumed``；同 turn 自重试或无法验证 turn 边界都 fail closed。
   *
   * input 未命中时若 ``debugSink`` 提供且存在同 session/tool 的其它条目，会输出
   * mismatch diff，帮助定位 LLM 改动了哪些字段。
   */
  consume(
    sessionId: string | undefined,
    toolName: string,
    input: unknown,
    turnId: string | undefined,
    debugSink?: (msg: string) => void,
  ): AskConsumeResult {
    this.maybeWarnGlobalFallback(sessionId, "consume", toolName);
    const key = AskApprovalCache.keyFor(sessionId, toolName, input);
    const entry = this.entries.get(key);
    if (!entry) {
      if (debugSink) this.debugWhyMiss(sessionId, toolName, input, debugSink);
      this.telemetry({
        event: "ask_consume_miss",
        toolName,
        sessionId: sessionId ?? null,
        reason: "no_entry",
        ts: new Date().toISOString(),
      });
      return "miss";
    }
    const latency_ms = Date.now() - entry.markedAt;
    // 双保险：即便 setTimeout 未触发，超时仍按未命中处理
    if (latency_ms > this.ttlMs) {
      clearTimeout(entry.timer);
      this.entries.delete(key);
      if (debugSink) debugSink(`AskCache: entry expired for ${toolName} (sid=${sessionId})`);
      this.telemetry({
        event: "ask_consume_miss",
        toolName,
        sessionId: sessionId ?? null,
        reason: "expired_double_check",
        latency_ms,
        ts: new Date().toISOString(),
      });
      return "miss";
    }
    if (!entry.turnId || !turnId) {
      if (debugSink) {
        debugSink(
          `AskCache: cannot verify a new user turn for ${toolName} (sid=${sessionId}); ` +
            "refusing to consume approval",
        );
      }
      this.telemetry({
        event: "ask_consume_miss",
        toolName,
        sessionId: sessionId ?? null,
        reason: "missing_turn_id",
        latency_ms,
        ts: new Date().toISOString(),
      });
      return "missing_turn_id";
    }
    if (entry.turnId === turnId) {
      if (debugSink) {
        debugSink(
          `AskCache: same user turn retried ${toolName} (sid=${sessionId}); ` +
            "waiting for a new user message",
        );
      }
      this.telemetry({
        event: "ask_consume_miss",
        toolName,
        sessionId: sessionId ?? null,
        reason: "same_turn",
        latency_ms,
        ts: new Date().toISOString(),
      });
      return "same_turn";
    }
    clearTimeout(entry.timer);
    this.entries.delete(key);
    this.telemetry({
      event: "ask_consumed",
      toolName,
      sessionId: sessionId ?? null,
      latency_ms,
      ts: new Date().toISOString(),
    });
    return "consumed";
  }

  /** 未命中时尝试找同 sid+tool 但 input 不同的条目，打 diff 帮排查。 */
  private debugWhyMiss(
    sessionId: string | undefined,
    toolName: string,
    input: unknown,
    sink: (msg: string) => void,
  ): void {
    const sid = sessionId && sessionId.length > 0 ? sessionId : "__global__";
    const prefix = `${sid}::${toolName}::`;
    const candidates: string[] = [];
    for (const k of this.entries.keys()) {
      if (k.startsWith(prefix)) candidates.push(k.slice(prefix.length));
    }
    if (candidates.length === 0) {
      sink(
        `AskCache miss: no prior mark for sid=${sid} tool=${toolName} ` +
          `(possible cause: different sessionId between calls / first call wasn't ask)`,
      );
      return;
    }
    const got = stableStringify(input);
    sink(
      `AskCache miss: sid=${sid} tool=${toolName} input mismatch.\n` +
        `  retry sent: ${got}\n` +
        `  prior had: ${candidates.join(" | ")}`,
    );
  }

  /** 当前活跃条目数（监控 / 测试用）。 */
  size(): number {
    return this.entries.size;
  }

  /** 测试 / shutdown：清空。 */
  clear(): void {
    for (const entry of this.entries.values()) {
      clearTimeout(entry.timer);
    }
    this.entries.clear();
  }
}

/** 进程内单例，被 with-hooks 默认使用。 */
export const defaultAskCache = new AskApprovalCache();
