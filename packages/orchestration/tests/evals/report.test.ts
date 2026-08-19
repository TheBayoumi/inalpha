import { describe, expect, it } from "vitest";

import { redactReportValue } from "../../src/evals/report.js";

describe("agent eval report redaction", () => {
  it("removes nested credentials and approval tokens", () => {
    expect(
      redactReportValue({
        approvalToken: "token-value",
        nested: {
          api_key: "key-value",
          headers: { authorization: "Bearer secret" },
          safe: "visible",
        },
      }),
    ).toEqual({
      approvalToken: "[REDACTED]",
      nested: {
        api_key: "[REDACTED]",
        headers: "[REDACTED]",
        safe: "visible",
      },
    });
  });
});
