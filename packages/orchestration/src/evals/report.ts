import { summarizeTasks } from "./report-stats.js";
import type {
  EvalFailureClass,
  EvalSuiteReport,
  EvalTrialResult,
} from "./types.js";

/** 汇总 trial，并保留稳定 schema 供 CI artifact 与后续 Dataset adapter 使用。 */
export function buildSuiteReport(
  suite: string,
  results: EvalTrialResult[],
): EvalSuiteReport {
  const ordered = [...results].sort((left, right) => {
    if (left.taskId !== right.taskId) return left.taskId < right.taskId ? -1 : 1;
    return left.trial - right.trial;
  });
  const passedCount = ordered.filter((result) => result.passed).length;
  const safeResults = ordered.map(
    (result) => redactReportValue(result) as EvalTrialResult,
  );
  return {
    schemaVersion: "agent-eval-report.v1",
    suite,
    passed: passedCount === results.length,
    total: results.length,
    passedCount,
    failedCount: results.length - passedCount,
    errors: [],
    taskSummaries: summarizeTasks(ordered),
    results: safeResults,
  };
}

/** 在 task 尚未执行时生成仍可上传的结构化失败报告。 */
export function buildFailedSuiteReport(
  suite: string,
  failureClass: EvalFailureClass,
  message: string,
): EvalSuiteReport {
  return {
    schemaVersion: "agent-eval-report.v1",
    suite,
    passed: false,
    total: 0,
    passedCount: 0,
    failedCount: 0,
    errors: [
      {
        failureClass,
        message: redactReportValue(message) as string,
      },
    ],
    taskSummaries: [],
    results: [],
  };
}

/** 递归移除报告中的凭证、审批 token 与 header。 */
export function redactReportValue(value: unknown): unknown {
  if (typeof value === "string") {
    return value
      .replace(/\bBearer\s+\S+/gi, "Bearer [REDACTED]")
      .replace(/\b(?:sk|key)-[A-Za-z0-9_-]{8,}/gi, "[REDACTED]")
      .replace(/\b(?:gh[pousr]_|github_pat_|xox[baprs]-)\S+/gi, "[REDACTED]");
  }
  if (Array.isArray(value)) return value.map(redactReportValue);
  if (!value || typeof value !== "object") return value;
  const redacted: Record<string, unknown> = {};
  const secretKey = /^(authorization|headers?|api_?key|client_?secret|private_?key|password|cookies?|set_?cookie|secret|(?:approval|auth|access|refresh|session|id)?_?token|stack|cause|provider_?metadata)$/i;
  for (const [key, field] of Object.entries(value as Record<string, unknown>)) {
    redacted[key] = secretKey.test(key) ? "[REDACTED]" : redactReportValue(field);
  }
  return redacted;
}

/** 输出适合终端阅读的单行摘要。 */
export function formatTrialSummary(result: EvalTrialResult): string {
  const mark = result.passed ? "PASS" : "FAIL";
  const failure = result.failureClass ? ` ${result.failureClass}` : "";
  return `${mark} ${result.taskId}#${result.trial}${failure} ` +
    `steps=${result.metrics.steps} calls=${result.metrics.toolCalls} ` +
    `latency=${result.metrics.latencyMs}ms`;
}
