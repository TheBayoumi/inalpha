import { describe, expect, it } from "vitest";

import { toMastraDatasetItem } from "../../src/evals/dataset-item.js";
import { GoldenTaskSchema } from "../../src/evals/schema.js";

function validTask(): Record<string, unknown> {
  return {
    schemaVersion: "agent-eval.v1",
    taskVersion: 1,
    id: "valid-task",
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

describe("GoldenTaskSchema", () => {
  it("accepts a complete versioned task", () => {
    expect(GoldenTaskSchema.safeParse(validTask()).success).toBe(true);
  });

  it("rejects unknown top-level fields", () => {
    expect(
      GoldenTaskSchema.safeParse({ ...validTask(), unexpected: true }).success,
    ).toBe(false);
  });

  it("rejects duplicate fixture tools", () => {
    const task = validTask();
    task.fixtures = {
      modelTurns: [{ type: "text", text: "done" }],
      tools: [
        { id: "data.read", description: "read", behavior: { type: "return", value: 1 } },
        { id: "data.read", description: "read", behavior: { type: "return", value: 2 } },
      ],
    };
    expect(GoldenTaskSchema.safeParse(task).success).toBe(false);
  });

  it("rejects undeclared scripted tools and non-terminal scripts", () => {
    const task = validTask();
    task.fixtures = {
      modelTurns: [
        { type: "tool-call", call: { tool: "data.missing", input: {} } },
      ],
      tools: [],
    };
    expect(GoldenTaskSchema.safeParse(task).success).toBe(false);
  });

  it("rejects an intermediate text turn that would stop the loop early", () => {
    const task = validTask();
    task.fixtures = {
      modelTurns: [
        { type: "text", text: "premature" },
        { type: "text", text: "final" },
      ],
      tools: [],
    };
    expect(GoldenTaskSchema.safeParse(task).success).toBe(false);
  });

  it("requires live tasks to belong to the live suite", () => {
    expect(
      GoldenTaskSchema.safeParse({
        ...validTask(),
        mode: "live",
        suites: ["nightly"],
      }).success,
    ).toBe(false);
  });

  it("maps the git fixture to Mastra Dataset fields", () => {
    const task = GoldenTaskSchema.parse(validTask());
    expect(toMastraDatasetItem(task)).toMatchObject({
      input: { prompt: "test", asOf: "2026-08-18T09:00:00Z" },
      groundTruth: task.expected.outcome,
      expectedTrajectory: task.expected.trajectory,
      metadata: { taskId: "valid-task", taskVersion: 1 },
    });
  });
});
