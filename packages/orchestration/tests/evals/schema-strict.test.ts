import { describe, expect, it } from "vitest";

import { GoldenTaskSchema } from "../../src/evals/schema.js";

function validTask(): Record<string, unknown> {
  return {
    schemaVersion: "agent-eval.v1",
    taskVersion: 1,
    id: "strict-task",
    mode: "scripted",
    suites: ["pr"],
    tags: [],
    prompt: "test",
    asOf: "2026-08-18T09:00:00Z",
    requestContext: {},
    fixtures: {
      modelTurns: [{ type: "text", text: "done" }],
      tools: [],
    },
    expected: {
      outcome: { includesAll: [], includesNone: [] },
      trajectory: {
        requiredCalls: [],
        orderedTools: [],
        forbiddenAttemptedTools: [],
        forbiddenExecutedTools: [],
      },
    },
    budget: { maxSteps: 2, maxToolCalls: 0, timeoutMs: 1000 },
  };
}

describe("GoldenTaskSchema fail-closed fields", () => {
  it("rejects incomplete and nested unknown fields", () => {
    const incomplete = validTask();
    delete incomplete.requestContext;
    expect(GoldenTaskSchema.safeParse(incomplete).success).toBe(false);

    const nestedUnknown = validTask();
    nestedUnknown.expected = {
      outcome: { includesAll: [], includesNone: [], unexpected: true },
      trajectory: {
        requiredCalls: [],
        orderedTools: [],
        forbiddenAttemptedTools: [],
        forbiddenExecutedTools: [],
      },
    };
    expect(GoldenTaskSchema.safeParse(nestedUnknown).success).toBe(false);
  });

  it("requires result classes and valid budgets", () => {
    const missingResult = validTask();
    missingResult.fixtures = {
      modelTurns: [
        { type: "tool-call", call: { tool: "data.read", input: {} } },
        { type: "text", text: "done" },
      ],
      tools: [
        {
          id: "data.read",
          description: "read",
          behavior: { type: "return", value: {} },
        },
      ],
    };
    missingResult.expected = {
      outcome: { includesAll: [], includesNone: [] },
      trajectory: {
        requiredCalls: [{ tool: "data.read" }],
        orderedTools: [],
        forbiddenAttemptedTools: [],
        forbiddenExecutedTools: [],
      },
    };
    expect(GoldenTaskSchema.safeParse(missingResult).success).toBe(false);

    const invalidBudget = validTask();
    invalidBudget.budget = { maxSteps: 0, maxToolCalls: -1, timeoutMs: 99 };
    expect(GoldenTaskSchema.safeParse(invalidBudget).success).toBe(false);
  });

  it("allows empty live fixtures and rejects scripted live turns", () => {
    const live = {
      ...validTask(),
      mode: "live",
      suites: ["live"],
      fixtures: { modelTurns: [], tools: [] },
    };
    expect(GoldenTaskSchema.safeParse(live).success).toBe(true);
    expect(
      GoldenTaskSchema.safeParse({
        ...live,
        fixtures: { modelTurns: [{ type: "text", text: "scripted" }], tools: [] },
      }).success,
    ).toBe(false);
  });
});
