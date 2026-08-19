import type { FullOutput } from "@mastra/core/stream";

import type { ResultClass } from "./schema.js";
import type { NormalizedToolCall, ToolExecutionEvent } from "./types.js";

/** 将 Mastra FullOutput 转换为稳定、可评分的工具轨迹。 */
export function normalizeTrajectory(
  output: FullOutput,
  executions: readonly ToolExecutionEvent[],
): NormalizedToolCall[] {
  const results = new Map<string, { result: unknown; isError?: boolean }>();
  for (const step of output.steps) {
    for (const chunk of step.toolResults) {
      results.set(chunk.payload.toolCallId, {
        result: chunk.payload.result,
        isError: chunk.payload.isError,
      });
    }
  }

  const executionKeys = executions.map(
    (event) => `${event.tool}:${stableStringify(event.input)}`,
  );
  const trajectory: NormalizedToolCall[] = [];
  for (const [stepIndex, step] of output.steps.entries()) {
    for (const chunk of step.toolCalls) {
      const payload = chunk.payload;
      const result = results.get(payload.toolCallId);
      const executionKey = `${payload.toolName}:${stableStringify(payload.args ?? {})}`;
      const executionIndex = executionKeys.indexOf(executionKey);
      const executed = executionIndex >= 0;
      if (executed) executionKeys.splice(executionIndex, 1);
      trajectory.push({
        index: trajectory.length,
        step: stepIndex,
        tool: payload.toolName,
        input: sanitizeValue(payload.args ?? {}),
        result: sanitizeValue(result?.result),
        resultClass: classifyResult(result?.result, result?.isError, executed),
        attempted: true,
        executed,
      });
    }
  }
  return trajectory;
}

/** 根据 wrapper 的结构化错误字段归一化结果。 */
export function classifyResult(
  result: unknown,
  chunkIsError: boolean | undefined,
  executed: boolean,
): ResultClass {
  if (result && typeof result === "object") {
    const record = result as Record<string, unknown>;
    if (record.requiresApproval === true || record.deniedBy === "permission-ask") {
      return "approval_required";
    }
    if (record.deniedBy === "permission") return "permission_deny";
    if (record.deniedBy === "hook" || record.deniedBy === "middleware-error") {
      return "middleware_error";
    }
    if (record.isError === true) return "tool_error";
  }
  if (chunkIsError) return "tool_error";
  return executed ? "success" : "tool_error";
}

/** 深度排序 JSON key，并移除报告中不应出现的敏感/非稳定字段。 */
export function sanitizeValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizeValue);
  if (!value || typeof value !== "object") return value;
  const output: Record<string, unknown> = {};
  const blocked = /^(authorization|headers|apiKey|api_key|secret|stack|cause)$/i;
  for (const key of Object.keys(value as Record<string, unknown>).sort()) {
    output[key] = blocked.test(key)
      ? "[REDACTED]"
      : sanitizeValue((value as Record<string, unknown>)[key]);
  }
  return output;
}

/** 为轨迹关联产生稳定 JSON。 */
export function stableStringify(value: unknown): string {
  return JSON.stringify(sanitizeValue(value));
}
