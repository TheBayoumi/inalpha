import { describe, expect, it } from "vitest";

import { AUTH_SUB_KEY } from "../../src/hooks/with-hooks.js";
import { createEvalRequestContext } from "../../src/evals/runner-context.js";
import { GoldenTaskSchema } from "../../src/evals/schema.js";
import { makeValidGoldenTask } from "./task-fixture.js";

describe("agent eval request context", () => {
  it("overrides trusted identity and asOf while preserving custom fields", () => {
    const task = GoldenTaskSchema.parse(
      makeValidGoldenTask({
        id: "context-precedence",
        asOf: "2026-08-18T09:00:00Z",
        requestContext: {
          [AUTH_SUB_KEY]: "spoofed",
          asOf: "1999-01-01T00:00:00Z",
          locale: "zh-CN",
        },
      }),
    );
    const context = createEvalRequestContext(task);

    expect(context.get(AUTH_SUB_KEY)).toBe("eval:context-precedence");
    expect(context.get("asOf")).toBe("2026-08-18T09:00:00Z");
    expect(context.get("locale")).toBe("zh-CN");
  });
});
