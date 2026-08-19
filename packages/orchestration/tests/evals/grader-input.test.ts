import { describe, expect, it } from "vitest";

import { gradeTrial } from "../../src/evals/grader.js";
import { GoldenTaskSchema } from "../../src/evals/schema.js";
import { makeValidGoldenTask } from "./task-fixture.js";

describe("agent eval required input subsets", () => {
  it("rejects a matching tool whose nested input differs", () => {
    const task = GoldenTaskSchema.parse(
      makeValidGoldenTask({
        fixtures: {
          modelTurns: [{ type: "text", text: "done" }],
          tools: [
            {
              id: "data.read",
              description: "read",
              behavior: { type: "return", value: {} },
            },
          ],
        },
        expected: {
          outcome: { includesAll: ["done"], includesNone: [] },
          trajectory: {
            requiredCalls: [
              {
                tool: "data.read",
                inputSubset: { query: { symbol: "AAPL" } },
                result: "success",
              },
            ],
            orderedTools: [],
            forbiddenAttemptedTools: [],
            forbiddenExecutedTools: [],
          },
        },
      }),
    );
    const findings = gradeTrial({
      task,
      text: "done",
      steps: 1,
      trajectory: [
        {
          index: 0,
          step: 0,
          tool: "data.read",
          input: { query: { symbol: "MSFT" } },
          result: {},
          resultClass: "success",
          attempted: true,
          executed: true,
        },
      ],
    });

    expect(findings).toContainEqual(
      expect.objectContaining({
        passed: false,
        message: "required call missing: data.read",
      }),
    );
  });
});
