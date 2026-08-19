import { describe, expect, it } from "vitest";

import {
  buildSuiteReport,
  redactReportValue,
} from "../../src/evals/report.js";
import type { EvalTrialResult } from "../../src/evals/types.js";

function trial(
  taskId: string,
  trialNumber: number,
  passed: boolean,
  latencyMs: number,
  totalTokens: number | null,
): EvalTrialResult {
  return {
    taskId,
    taskVersion: 1,
    trial: trialNumber,
    passed,
    failureClass: passed ? null : "outcome_mismatch",
    findings: [],
    text: "done",
    trajectory: [],
    metrics: {
      steps: 1,
      toolCalls: 0,
      inputTokens: totalTokens === null ? null : 1,
      outputTokens: totalTokens === null ? null : totalTokens - 1,
      totalTokens,
      latencyMs,
      costUsd: null,
    },
    model: { provider: "scripted", modelId: taskId },
    runId: `eval:${taskId}:${trialNumber}`,
    traceId: null,
  };
}

describe("agent eval report", () => {
  it("removes nested credentials and unstable error metadata", () => {
    const githubToken = ["ghp", "abcdefghijklmnopqrstuvwxyz"].join("_");
    expect(
      redactReportValue({
        approvalToken: "token-value",
        nested: {
          api_key: "key-value",
          header: { authorization: "Bearer secret" },
          client_secret: "hidden",
          privateKey: "hidden",
          password: "hidden",
          cookie: "hidden",
          token: "hidden",
          providerMetadata: { requestId: "hidden" },
          stack: "hidden",
          safe: "visible",
        },
        message: `token ${githubToken}`,
      }),
    ).toEqual({
      approvalToken: "[REDACTED]",
      nested: {
        api_key: "[REDACTED]",
        header: "[REDACTED]",
        client_secret: "[REDACTED]",
        privateKey: "[REDACTED]",
        password: "[REDACTED]",
        cookie: "[REDACTED]",
        token: "[REDACTED]",
        providerMetadata: "[REDACTED]",
        stack: "[REDACTED]",
        safe: "visible",
      },
      message: "token [REDACTED]",
    });
  });

  it("sorts trials and reports pass-rate, latency, and token variance", () => {
    const report = buildSuiteReport("live", [
      trial("task-b", 1, true, 5, null),
      trial("task-a", 2, false, 30, 6),
      trial("task-a", 1, true, 10, 2),
    ]);

    expect(report.results.map((result) => `${result.taskId}#${result.trial}`))
      .toEqual(["task-a#1", "task-a#2", "task-b#1"]);
    expect(report.taskSummaries[0]).toEqual({
      taskId: "task-a",
      trials: 2,
      passedCount: 1,
      passRate: 0.5,
      latencyMeanMs: 20,
      latencyVarianceMs2: 100,
      totalTokensMean: 4,
      totalTokensVariance: 4,
    });
    expect(report).toMatchObject({ passed: false, total: 3, passedCount: 2 });
  });
});
