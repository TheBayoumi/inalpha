import { describe, expect, it } from "vitest";

import { buildFailedSuiteReport } from "../../src/evals/report.js";

describe("agent eval pre-execution failure report", () => {
  it("keeps trial counters consistent and redacts the error", () => {
    const secret = ["secret", "value"].join("-");
    const report = buildFailedSuiteReport(
      "pr",
      "fixture_invalid",
      `Bearer ${secret}`,
    );

    expect(report).toMatchObject({
      passed: false,
      total: 0,
      passedCount: 0,
      failedCount: 0,
      errors: [
        {
          failureClass: "fixture_invalid",
          message: "Bearer [REDACTED]",
        },
      ],
      results: [],
    });
    expect(report.total).toBe(report.passedCount + report.failedCount);
    expect(JSON.stringify(report)).not.toContain(secret);
  });
});
