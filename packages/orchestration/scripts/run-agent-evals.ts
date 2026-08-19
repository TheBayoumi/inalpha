import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { loadGoldenTasks } from "../src/evals/load.js";
import { buildSuiteReport, formatTrialSummary } from "../src/evals/report.js";
import { runEvalTrial } from "../src/evals/runner.js";
import { EvalSuiteSchema, type GoldenTask } from "../src/evals/schema.js";
import type { EvalTrialResult, RunTrialOptions } from "../src/evals/types.js";

const args = parseArgs(process.argv.slice(2));
const suite = EvalSuiteSchema.parse(args.suite ?? "pr");
const goldenDir = fileURLToPath(new URL("../evals/golden/", import.meta.url));

try {
  let tasks = await loadGoldenTasks(goldenDir, suite);
  if (args.caseId) tasks = tasks.filter((task) => task.id === args.caseId);
  if (tasks.length === 0) throw new Error(`eval case not found: ${args.caseId}`);
  const trials = parseTrials(args.trials, suite);
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

function parseTrials(raw: string | undefined, suite: string): number {
  const value = raw === undefined ? (suite === "live" ? 3 : 1) : Number(raw);
  const valid = Number.isInteger(value) && value >= 1 && value <= (suite === "live" ? 5 : 1);
  if (!valid) throw new Error("trials must be 1 offline or 1..5 live");
  return value;
}

function parseArgs(values: string[]): {
  suite?: string;
  caseId?: string;
  trials?: string;
  report?: string;
} {
  const parsed: Record<string, string> = {};
  const args = values.filter((value) => value !== "--");
  const names: Record<string, string> = {
    "--suite": "suite",
    "--case": "caseId",
    "--trials": "trials",
    "--report": "report",
  };
  for (let index = 0; index < args.length; index += 2) {
    const key = names[args[index] ?? ""];
    const value = args[index + 1];
    if (!key || !value) throw new Error(`invalid eval argument: ${args[index] ?? ""}`);
    parsed[key] = value;
  }
  return parsed;
}
