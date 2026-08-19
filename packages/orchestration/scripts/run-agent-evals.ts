import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { parseEvalArgs, parseTrialCount } from "../src/evals/cli.js";
import { loadGoldenTasks } from "../src/evals/load.js";
import { buildSuiteReport, formatTrialSummary } from "../src/evals/report.js";
import { runEvalTrial } from "../src/evals/runner.js";
import { EvalSuiteSchema, type GoldenTask } from "../src/evals/schema.js";
import type { EvalTrialResult, RunTrialOptions } from "../src/evals/types.js";

const args = parseEvalArgs(process.argv.slice(2));
const suite = EvalSuiteSchema.parse(args.suite ?? "pr");
const goldenDir = fileURLToPath(new URL("../evals/golden/", import.meta.url));

try {
  let tasks = await loadGoldenTasks(goldenDir, suite);
  if (args.caseId) tasks = tasks.filter((task) => task.id === args.caseId);
  if (tasks.length === 0) throw new Error(`eval case not found: ${args.caseId}`);
  const trials = parseTrialCount(args.trials, suite);
  if (suite === "live" && !args.caseId) {
    throw new Error("live eval requires --case <task-id>");
  }

  const results: EvalTrialResult[] = [];
  for (const task of tasks) {
    for (let trial = 1; trial <= trials; trial += 1) {
      const options = await trialOptions(task, trial, suite === "live");
      const result = await runEvalTrial(task, options);
      results.push(result);
      console.log(formatTrialSummary(result));
    }
  }

  const report = buildSuiteReport(suite, results);
  if (args.report) {
    await mkdir(dirname(args.report), { recursive: true });
    await writeFile(args.report, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  }
  console.log(
    `Agent eval ${suite}: ${report.passedCount}/${report.total} passed`,
  );
  if (!report.passed) process.exitCode = 1;
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

async function trialOptions(
  task: GoldenTask,
  trial: number,
  live: boolean,
): Promise<RunTrialOptions> {
  if (!live) return { trial };
  if (process.env.INALPHA_AGENT_EVAL_LIVE !== "1") {
    throw new Error("live eval requires INALPHA_AGENT_EVAL_LIVE=1");
  }
  const { buildLLM } = await import("../src/mastra/llm/provider.js");
  const provider = process.env.LLM_PROVIDER?.trim();
  const modelId = process.env.LLM_MODEL?.trim();
  if (!provider || !modelId) {
    throw new Error("live eval requires explicit LLM_PROVIDER and LLM_MODEL");
  }
  if (task.mode !== "live") throw new Error(`not a live task: ${task.id}`);
  return {
    trial,
    model: buildLLM(),
    modelDescriptor: { provider, modelId },
    allowNetwork: true,
  };
}
