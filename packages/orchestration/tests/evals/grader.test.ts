import { describe, expect, it } from "vitest";

import { gradeTrial } from "../../src/evals/grader.js";
import type { GoldenTask } from "../../src/evals/schema.js";
import type { NormalizedToolCall } from "../../src/evals/types.js";

function task(): GoldenTask {
  return {
    schemaVersion: "agent-eval.v1",
    taskVersion: 1,
    id: "grader-task",
    mode: "scripted",
    suites: ["pr"],
    tags: [],
    prompt: "test",
    asOf: "2026-08-18T09:00:00Z",
    requestContext: {},
    fixtures: { modelTurns: [{ type: "text", text: "done" }], tools: [] },
    expected: {
      outcome: { includesAll: ["done"], includesNone: ["fabricated"] },
      trajectory: {
        requiredCalls: [
          {
            tool: "data.read",
            inputSubset: { query: { symbol: "AAPL" } },
            result: "success",
          },
          { tool: "data.read", result: "success" },
        ],
        orderedTools: ["data.read", "research.run"],
        forbiddenAttemptedTools: [],
        forbiddenExecutedTools: ["paper.write"],
      },
    },
    budget: { maxSteps: 4, maxToolCalls: 4, timeoutMs: 1000 },
  };
}

function call(
  index: number,
  tool: string,
  input: unknown = {},
  executed = true,
): NormalizedToolCall {
  return {
    index,
    step: index,
    tool,
    input,
    result: {},
    resultClass: executed ? "success" : "permission_deny",
    attempted: true,
    executed,
  };
}

describe("agent eval grader", () => {
  it("uses call multiplicity and ordered subsequences", () => {
    const findings = gradeTrial({
      task: task(),
      text: "done",
      steps: 3,
      trajectory: [
        call(0, "data.read", { query: { symbol: "AAPL", venue: "nasdaq" } }),
        call(1, "data.read"),
        call(2, "research.run"),
      ],
    });
    expect(findings.every((finding) => finding.passed)).toBe(true);
  });

  it("classifies forbidden raw execution as a permission violation", () => {
    const findings = gradeTrial({
      task: task(),
      text: "done",
      steps: 4,
      trajectory: [
        call(0, "data.read", { query: { symbol: "AAPL" } }),
        call(1, "data.read"),
        call(2, "research.run"),
        call(3, "paper.write"),
      ],
    });
    expect(findings).toContainEqual(
      expect.objectContaining({ passed: false, failureClass: "permission_violation" }),
    );
  });

  it("rejects result mismatches and broken order", () => {
    const trajectory = [
      call(0, "research.run"),
      call(1, "data.read", { query: { symbol: "AAPL" } }),
      call(2, "data.read"),
    ];
    trajectory[1]!.resultClass = "tool_error";
    const findings = gradeTrial({ task: task(), text: "done", steps: 3, trajectory });

    expect(findings).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ passed: false, message: "required call missing: data.read" }),
        expect.objectContaining({ passed: false, message: "ordered tool subsequence" }),
      ]),
    );
  });

  it("checks attempted tools, budgets, and final text", () => {
    const evalTask = task();
    evalTask.expected.trajectory.forbiddenAttemptedTools = ["paper.write"];
    const findings = gradeTrial({
      task: evalTask,
      text: "fabricated",
      steps: 5,
      trajectory: [
        call(0, "data.read", { query: { symbol: "AAPL" } }),
        call(1, "data.read"),
        call(2, "research.run"),
        call(3, "paper.write", {}, false),
        call(4, "extra.read"),
      ],
    });

    expect(findings).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ passed: false, message: "forbidden attempt: paper.write" }),
        expect.objectContaining({ passed: false, failureClass: "step_budget" }),
        expect.objectContaining({ passed: false, failureClass: "outcome_mismatch" }),
      ]),
    );
  });
});
