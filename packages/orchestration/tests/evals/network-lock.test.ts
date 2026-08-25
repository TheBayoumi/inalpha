import type { LanguageModel } from "@mastra/core/llm";
import { describe, expect, it, vi } from "vitest";

import { runEvalTrial } from "../../src/evals/runner.js";
import { GoldenTaskSchema } from "../../src/evals/schema.js";
import { makeValidGoldenTask } from "./task-fixture.js";

function delayedModel(onStart: () => void, onEnd: () => void): LanguageModel {
  return {
    specificationVersion: "v2",
    provider: "lock-test",
    modelId: "lock-test",
    supportedUrls: {},
    doGenerate: async () => {
      onStart();
      await new Promise((resolve) => setTimeout(resolve, 20));
      onEnd();
      return {
        content: [{ type: "text", text: "done" }],
        finishReason: "stop",
        usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2 },
        warnings: [],
        response: { id: "lock", modelId: "lock-test", timestamp: new Date(0) },
      };
    },
  } as unknown as LanguageModel;
}

describe("agent eval network guard lock", () => {
  it("serializes parallel trials and restores the original fetch", async () => {
    const originalFetch = globalThis.fetch;
    const baselineFetch = vi.fn(async () => new Response("baseline"));
    vi.stubGlobal("fetch", baselineFetch);
    let active = 0;
    let maxActive = 0;
    const model = () => delayedModel(
      () => {
        active += 1;
        maxActive = Math.max(maxActive, active);
      },
      () => {
        active -= 1;
      },
    );
    const task = GoldenTaskSchema.parse(
      makeValidGoldenTask({
        id: "parallel-lock",
        mode: "live",
        suites: ["live"],
        fixtures: { modelTurns: [], tools: [] },
        expected: {
          outcome: { includesAll: ["done"], includesNone: [] },
          trajectory: {
            requiredCalls: [],
            orderedTools: [],
            forbiddenAttemptedTools: [],
            forbiddenExecutedTools: [],
          },
        },
      }),
    );

    try {
      const results = await Promise.all([
        runEvalTrial(task, { trial: 1, model: model() }),
        runEvalTrial(task, { trial: 2, model: model() }),
      ]);
      expect(results.every((result) => result.passed)).toBe(true);
      expect(maxActive).toBe(1);
      expect(globalThis.fetch).toBe(baselineFetch);
      expect(baselineFetch).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
    }
    expect(globalThis.fetch).toBe(originalFetch);
  });
});
