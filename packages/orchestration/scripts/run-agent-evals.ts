import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import {
  classifyCliFailure,
  findReportPath,
  parseEvalArgs,
  parseTrialCount,
  type EvalCliArgs,
} from "../src/evals/cli.js";
import { EvalFailureError } from "../src/evals/errors.js";
import { loadGoldenTasks } from "../src/evals/load.js";
import {
  buildFailedSuiteReport,
  buildSuiteReport,
  formatTrialSummary,
} from "../src/evals/report.js";
import { runEvalTrial } from "../src/evals/runner.js";
import { EvalSuiteSchema, type GoldenTask } from "../src/evals/schema.js";
import type {
  EvalSuiteReport,
  EvalTrialResult,
  RunTrialOptions,
} from "../src/evals/types.js";

const rawArgs = process.argv.slice(2);
let args: EvalCliArgs = { report: findReportPath(rawArgs) };
const goldenDir = fileURLToPath(new URL("../evals/golden/", import.meta.url));

try {
  args = parseEvalArgs(rawArgs);
  const suite = EvalSuiteSchema.parse(args.suite ?? "pr");
  let tasks = await loadGoldenTasks(goldenDir, suite);
  if (args.caseId) tasks = tasks.filter((task) => task.id === args.caseId);
  if (tasks.length === 0) {
    throw new EvalFailureError(
      "fixture_invalid",
      `eval case not found: ${args.caseId}`,
    );
  }
  const trials = parseTrialCount(args.trials, suite);
  if (suite === "live" && !args.caseId) {
    throw new EvalFailureError(
      "live_provider",
      "live eval requires --case <task-id>",
    );
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
  if (args.report) await writeReport(args.report, report);
  console.log(
    `Agent eval ${suite}: ${report.passedCount}/${report.total} passed`,
  );
  if (!report.passed) process.exitCode = 1;
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  if (args.report) {
    const report = buildFailedSuiteReport(
      args.suite ?? "pr",
      classifyCliFailure(error),
      message,
    );
    try {
      await writeReport(args.report, report);
    } catch (reportError) {
      console.error(`failed to write eval report: ${String(reportError)}`);
    }
  }
  console.error(message);
  process.exitCode = 1;
}

async function writeReport(path: string, report: EvalSuiteReport): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(report, null, 2)}\n`, "utf8");
}

async function trialOptions(
  task: GoldenTask,
  trial: number,
  live: boolean,
): Promise<RunTrialOptions> {
  if (!live) return { trial };
  if (process.env.INALPHA_AGENT_EVAL_LIVE !== "1") {
    throw new EvalFailureError(
      "live_provider",
      "live eval requires INALPHA_AGENT_EVAL_LIVE=1",
    );
  }
  const provider = process.env.LLM_PROVIDER?.trim();
  const modelId = process.env.LLM_MODEL?.trim();
  if (!provider || !modelId) {
    throw new EvalFailureError(
      "live_provider",
      "live eval requires explicit LLM_PROVIDER and LLM_MODEL",
    );
  }
  if (task.mode !== "live") {
    throw new EvalFailureError("live_provider", `not a live task: ${task.id}`);
  }
  const { buildLLM } = await import("../src/mastra/llm/provider.js");
  return {
    trial,
    model: buildLLM(),
    modelDescriptor: { provider, modelId },
    allowNetwork: true,
  };
}
