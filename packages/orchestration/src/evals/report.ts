import type { EvalSuiteReport, EvalTrialResult } from "./types.js";

/** 汇总 trial，并保留稳定 schema 供 CI artifact 与后续 Dataset adapter 使用。 */
export function buildSuiteReport(
  suite: string,
  results: EvalTrialResult[],
): EvalSuiteReport {
  const passedCount = results.filter((result) => result.passed).length;
  const safeResults = results.map(
    (result) => redactReportValue(result) as EvalTrialResult,
  );
  return {
    schemaVersion: "agent-eval-report.v1",
    suite,
    passed: passedCount === results.length,
    total: results.length,
    passedCount,
    failedCount: results.length - passedCount,
    results: safeResults,
  };
}

/** 递归移除报告中的凭证、审批 token 与 header。 */
export function redactReportValue(value: unknown): unknown {
  if (typeof value === "string") {
    return value
      .replace(/\bBearer\s+\S+/gi, "Bearer [REDACTED]")
      .replace(/\b(?:sk|key)-[A-Za-z0-9_-]{8,}/g, "[REDACTED]");
  }
  if (Array.isArray(value)) return value.map(redactReportValue);
  if (!value || typeof value !== "object") return value;
  const redacted: Record<string, unknown> = {};
  const secretKey = /^(authorization|headers|api_?key|secret|approvalToken|authToken|accessToken|refreshToken)$/i;
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
