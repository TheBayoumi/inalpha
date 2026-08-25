import { fileURLToPath } from "node:url";

import type { LanguageModel } from "@mastra/core/llm";
import { afterEach, describe, expect, it, vi } from "vitest";

import { loadGoldenTasks } from "../../src/evals/load.js";
import { runEvalTrial } from "../../src/evals/runner.js";
import { GoldenTaskSchema } from "../../src/evals/schema.js";
import { makeValidGoldenTask } from "./task-fixture.js";

const goldenDir = fileURLToPath(new URL("../../evals/golden/", import.meta.url));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("agent eval runner guards", () => {
  it("isolates approval cache state between trials", async () => {
    const baselineFetch = vi.fn(async () => new Response("baseline"));
    vi.stubGlobal("fetch", baselineFetch);
    const tasks = await loadGoldenTasks(goldenDir, "pr");
    const task = tasks.find(
      (candidate) => candidate.id === "ask-first-attempt-fail-closed",
    );
    expect(task).toBeDefined();

    const first = await runEvalTrial(task!, { trial: 1 });
    const second = await runEvalTrial(task!, { trial: 2 });
    for (const result of [first, second]) {
      expect(result).toMatchObject({ passed: true });
      expect(result.trajectory[0]).toMatchObject({
        resultClass: "approval_required",
        executed: false,
      });
    }
    expect(baselineFetch).not.toHaveBeenCalled();
    expect(globalThis.fetch).toBe(baselineFetch);
  });

  it("blocks undeclared network access and restores fetch", async () => {
    const baselineFetch = vi.fn(async () => new Response("baseline"));
    vi.stubGlobal("fetch", baselineFetch);
    const task = GoldenTaskSchema.parse(
      makeValidGoldenTask({
        id: "runner-network-guard",
        prompt: "test network guard",
        fixtures: {
          modelTurns: [{ type: "text", text: "unused" }],
          tools: [],
        },
      }),
    );
    const networkModel = {
      specificationVersion: "v2",
      provider: "network-test",
      modelId: "network-test",
      supportedUrls: {},
      doGenerate: async () => {
        await fetch("https://example.test");
        throw new Error("network guard did not stop the request");
      },
    } as unknown as LanguageModel;

    const result = await runEvalTrial(task, { trial: 1, model: networkModel });
    expect(result).toMatchObject({ passed: false, failureClass: "network_attempt" });
    expect(baselineFetch).not.toHaveBeenCalled();
    expect(globalThis.fetch).toBe(baselineFetch);
  });

  it("fails closed when a live task has no explicit model", async () => {
    const [task] = await loadGoldenTasks(goldenDir, "live");
    const result = await runEvalTrial(task!, { trial: 1 });
    expect(result).toMatchObject({ passed: false, failureClass: "live_provider" });
  });
});
