import { describe, expect, it } from "vitest";

import {
  classifyFailure,
  selectFailureClass,
} from "../../src/evals/runner-helpers.js";

describe("agent eval failure classes", () => {
  it("maps network, tool schema, model, timeout, and internal failures", () => {
    expect(classifyFailure(new Error("EVAL_NETWORK_ATTEMPT")))
      .toBe("network_attempt");
    expect(classifyFailure(new Error("tool input schema validation error")))
      .toBe("tool_schema");
    expect(classifyFailure(new Error("scripted model extra call")))
      .toBe("model_protocol");
    expect(classifyFailure(new Error("eval item timeout"))).toBe("timeout");
    expect(classifyFailure(new Error("unknown"))).toBe("internal");
  });

  it("prioritizes permission violations over other findings", () => {
    expect(
      selectFailureClass([
        {
          passed: false,
          failureClass: "outcome_mismatch",
          message: "outcome",
        },
        {
          passed: false,
          failureClass: "permission_violation",
          message: "permission",
        },
      ]),
    ).toBe("permission_violation");
  });
});
