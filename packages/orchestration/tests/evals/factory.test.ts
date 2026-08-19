import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { ScriptedModel } from "../../src/evals/scripted-model.js";
import { createOrchestrator } from "../../src/mastra/agents/create-orchestrator.js";
import { orchestrator } from "../../src/mastra/agents/orchestrator.js";

const packageRoot = fileURLToPath(new URL("../../", import.meta.url));

describe("Orchestrator factory", () => {
  it("keeps eval Agents stateless and honors their step budget", async () => {
    const agent = createOrchestrator({
      model: new ScriptedModel("factory", [{ type: "text", text: "done" }])
        .asLanguageModel(),
      tools: {},
      maxSteps: 7,
    });

    expect(agent).toMatchObject({ id: "orchestrator", name: "orchestrator" });
    expect(await agent.getDefaultOptions()).toMatchObject({ maxSteps: 7 });
    expect(agent.hasOwnMemory()).toBe(false);
    expect(await agent.listConfiguredOutputProcessors()).toEqual([]);
    expect(
      (await agent.listConfiguredInputProcessors()).map((processor) => processor.id),
    ).toEqual(["token-limiter"]);
  });

  it("imports the factory without loading production env or storage", () => {
    const result = spawnSync(
      process.execPath,
      [
        "--import",
        "tsx",
        "--input-type=module",
        "--eval",
        "await import('./src/mastra/agents/create-orchestrator.ts')",
      ],
      { cwd: packageRoot, encoding: "utf8", timeout: 10_000 },
    );

    expect(result.status, result.stderr).toBe(0);
    expect(`${result.stdout}${result.stderr}`).not.toMatch(
      /\[(?:env|paths|mcp)\]/,
    );
  });

  it("preserves the production singleton configuration", async () => {
    expect(orchestrator).toMatchObject({ id: "orchestrator", name: "orchestrator" });
    expect(await orchestrator.getDefaultOptions()).toMatchObject({ maxSteps: 40 });
    expect(orchestrator.hasOwnMemory()).toBe(true);
    expect(
      (await orchestrator.listConfiguredOutputProcessors()).map(
        (processor) => processor.id,
      ),
    ).toEqual(["pending-plan-notice"]);
  });
});
