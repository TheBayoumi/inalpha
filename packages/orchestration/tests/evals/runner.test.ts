import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { loadGoldenTasks } from "../../src/evals/load.js";
import { runEvalTrial } from "../../src/evals/runner.js";
import { GoldenTaskSchema } from "../../src/evals/schema.js";

const goldenDir = fileURLToPath(new URL("../../evals/golden/", import.meta.url));

describe("agent eval runner", () => {
  it("runs every PR task through the real Mastra loop", async () => {
    const tasks = await loadGoldenTasks(goldenDir, "pr");
    const results = [];
    for (const task of tasks) {
      results.push(await runEvalTrial(task, { trial: 1 }));
    }

    expect(
      results.every((result) => result.passed),
      results
        .flatMap((result) =>
          result.findings
            .filter((finding) => !finding.passed)
            .map((finding) => `${result.taskId}: ${finding.message}`),
        )
        .join("\n"),
    ).toBe(true);

    const directOrder = results.find(
      (result) => result.taskId === "permission-direct-order-denied",
    );
    expect(directOrder?.trajectory).toEqual([
      expect.objectContaining({
        tool: "paper.submit_order_intent",
        resultClass: "permission_deny",
        attempted: true,
        executed: false,
      }),
    ]);
  });

  it("aborts an item that exceeds its timeout budget", async () => {
    const task = GoldenTaskSchema.parse({
      schemaVersion: "agent-eval.v1",
      taskVersion: 1,
      id: "runner-timeout",
      mode: "scripted",
      suites: ["pr"],
      tags: [],
      prompt: "read data",
      asOf: "2026-08-18T09:00:00Z",
      requestContext: {},
      fixtures: {
        modelTurns: [
          { type: "tool-call", call: { tool: "data.get_bars", input: {} } },
          { type: "text", text: "done" },
        ],
        tools: [
          {
            id: "data.get_bars",
            description: "Delayed synthetic read used to verify the item timeout.",
            behavior: { type: "delay", delayMs: 500, value: {} },
          },
        ],
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
      budget: { maxSteps: 3, maxToolCalls: 1, timeoutMs: 100 },
    });

    const result = await runEvalTrial(task, { trial: 1 });
    expect(result).toMatchObject({ passed: false, failureClass: "timeout" });
  });
});
