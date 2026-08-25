import { describe, expect, it } from "vitest";

import { toMastraDatasetItem } from "../../src/evals/dataset-item.js";
import { GoldenTaskSchema } from "../../src/evals/schema.js";
import { makeValidGoldenTask } from "./task-fixture.js";

describe("GoldenTaskSchema", () => {
  it("accepts a complete versioned task", () => {
    expect(GoldenTaskSchema.safeParse(makeValidGoldenTask()).success).toBe(true);
  });

  it("rejects unknown top-level fields", () => {
    expect(
      GoldenTaskSchema.safeParse({ ...makeValidGoldenTask(), unexpected: true }).success,
    ).toBe(false);
  });

  it("rejects duplicate fixture tools", () => {
    const task = makeValidGoldenTask();
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
    const task = makeValidGoldenTask();
    task.fixtures = {
      modelTurns: [
        { type: "tool-call", call: { tool: "data.missing", input: {} } },
      ],
      tools: [],
    };
    expect(GoldenTaskSchema.safeParse(task).success).toBe(false);
  });

  it("rejects an intermediate text turn that would stop the loop early", () => {
    const task = makeValidGoldenTask();
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
        ...makeValidGoldenTask(),
        mode: "live",
        suites: ["nightly"],
      }).success,
    ).toBe(false);
  });

  it("maps the git fixture to Mastra Dataset fields", () => {
    const task = GoldenTaskSchema.parse(makeValidGoldenTask());
    expect(toMastraDatasetItem(task)).toMatchObject({
      input: { prompt: "test", asOf: "2026-08-18T09:00:00Z" },
      groundTruth: task.expected.outcome,
      expectedTrajectory: task.expected.trajectory,
      metadata: { taskId: "valid-task", taskVersion: 1 },
    });
  });
});
