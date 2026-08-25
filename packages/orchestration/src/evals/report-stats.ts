import type { EvalTaskSummary, EvalTrialResult } from "./types.js";

/** 按 task 汇总 pass rate、延迟与 token 方差。 */
export function summarizeTasks(results: EvalTrialResult[]): EvalTaskSummary[] {
  const groups = new Map<string, EvalTrialResult[]>();
  for (const result of results) {
    const group = groups.get(result.taskId) ?? [];
    group.push(result);
    groups.set(result.taskId, group);
  }
  return [...groups.entries()].map(([taskId, trials]) => {
    const latencies = trials.map((trial) => trial.metrics.latencyMs);
    const tokens = trials.flatMap((trial) =>
      trial.metrics.totalTokens === null ? [] : [trial.metrics.totalTokens]
    );
    const passedCount = trials.filter((trial) => trial.passed).length;
    return {
      taskId,
      trials: trials.length,
      passedCount,
      passRate: passedCount / trials.length,
      latencyMeanMs: mean(latencies) ?? 0,
      latencyVarianceMs2: variance(latencies) ?? 0,
      totalTokensMean: mean(tokens),
      totalTokensVariance: variance(tokens),
    };
  });
}

function mean(values: number[]): number | null {
  return values.length === 0
    ? null
    : values.reduce((total, value) => total + value, 0) / values.length;
}

function variance(values: number[]): number | null {
  const average = mean(values);
  return average === null
    ? null
    : values.reduce((total, value) => total + (value - average) ** 2, 0) /
      values.length;
}
