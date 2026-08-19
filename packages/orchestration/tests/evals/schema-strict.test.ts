import { describe, expect, it } from "vitest";

import { GoldenTaskSchema } from "../../src/evals/schema.js";
import { makeValidGoldenTask } from "./task-fixture.js";

describe("GoldenTaskSchema fail-closed fields", () => {
  it("rejects incomplete and nested unknown fields", () => {
    const incomplete = makeValidGoldenTask();
    delete incomplete.requestContext;
    expect(GoldenTaskSchema.safeParse(incomplete).success).toBe(false);

    const nestedUnknown = makeValidGoldenTask();
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
    const missingResult = makeValidGoldenTask();
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

    const invalidBudget = makeValidGoldenTask();
    invalidBudget.budget = { maxSteps: 0, maxToolCalls: -1, timeoutMs: 99 };
    expect(GoldenTaskSchema.safeParse(invalidBudget).success).toBe(false);
  });

  it("requires a valid timezone-aware asOf", () => {
    for (const asOf of [
      "2026-08-18T09:00:00",
      "2026-08-18",
      "2026-13-18T09:00:00Z",
      1,
    ]) {
      expect(GoldenTaskSchema.safeParse({ ...makeValidGoldenTask(), asOf }).success).toBe(false);
    }
    expect(
      GoldenTaskSchema.safeParse({
        ...makeValidGoldenTask(),
        asOf: "2026-08-18T17:00:00+08:00",
      }).success,
    ).toBe(true);
  });

  it("allows empty live fixtures and rejects scripted live turns", () => {
    const live = {
      ...makeValidGoldenTask(),
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
