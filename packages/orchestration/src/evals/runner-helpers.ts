import type { GoldenTask } from "./schema.js";
import { classifyEvalError, EvalFailureError } from "./errors.js";
import type {
  EvalFailureClass,
  EvalTrialResult,
  GradeFinding,
  RunTrialOptions,
} from "./types.js";

let networkGuardTail = Promise.resolve();

/** 串行化进程级 fetch 替换，避免并行 trial 互相污染。 */
export async function acquireNetworkGuardLock(): Promise<() => void> {
  let releaseLock: () => void = () => undefined;
  const current = new Promise<void>((resolve) => {
    releaseLock = resolve;
  });
  const previous = networkGuardTail;
  networkGuardTail = previous.then(() => current);
  await previous;
  let released = false;
  return () => {
    if (released) return;
    released = true;
    releaseLock();
  };
}

/** Required lane 禁止任何未声明网络请求，并返回恢复函数。 */
export function installNetworkGuard(allow: boolean): () => void {
  if (allow) return () => undefined;
  const original = globalThis.fetch;
  globalThis.fetch = (async () => {
    throw new EvalFailureError("network_attempt", "EVAL_NETWORK_ATTEMPT");
  }) as typeof fetch;
  return () => {
    globalThis.fetch = original;
  };
}

/** 选择最严重的确定性评分失败。 */
export function selectFailureClass(
  findings: GradeFinding[],
): EvalFailureClass | null {
  const classes = findings
    .filter((finding) => !finding.passed)
    .map((finding) => finding.failureClass);
  if (classes.includes("permission_violation")) return "permission_violation";
  return classes.find((value): value is EvalFailureClass => value !== undefined) ?? null;
}

/** 从不稳定 provider usage 中安全读取数值字段。 */
export function numberField(value: unknown, key: string): number | null {
  if (!value || typeof value !== "object") return null;
  const field = (value as Record<string, unknown>)[key];
  return typeof field === "number" ? field : null;
}

/** 将 runtime 异常归类为稳定失败码。 */
export function classifyFailure(error: unknown): EvalFailureClass {
  return classifyEvalError(error);
}

/** 生成在 Agent 尚未返回 FullOutput 时使用的失败结果。 */
export function failedResult(
  task: GoldenTask,
  options: RunTrialOptions,
  started: number,
  failureClass: EvalFailureClass,
  message: string,
): EvalTrialResult {
  return {
    taskId: task.id,
    taskVersion: task.taskVersion,
    trial: options.trial,
    passed: false,
    failureClass,
    findings: [{ passed: false, failureClass, message }],
    text: "",
    trajectory: [],
    metrics: {
      steps: 0,
      toolCalls: 0,
      inputTokens: null,
      outputTokens: null,
      totalTokens: null,
      latencyMs: Math.round(performance.now() - started),
      costUsd: null,
    },
    model: options.modelDescriptor ?? { provider: "unknown", modelId: "unknown" },
    runId: `eval:${task.id}:${options.trial}`,
    traceId: null,
  };
}

/** 保留 Error 信息并兼容任意 throw 值。 */
export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
