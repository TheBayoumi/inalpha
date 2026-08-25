import type { GoldenTask } from "./schema.js";

/** Mastra Dataset.addItem 接受的稳定字段集合。 */
export type MastraDatasetItem = {
  input: unknown;
  groundTruth: unknown;
  expectedTrajectory: unknown;
  requestContext: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

/** 将 git 中的 Golden Task 映射为 Mastra Dataset item，不执行持久化。 */
export function toMastraDatasetItem(task: GoldenTask): MastraDatasetItem {
  return {
    input: {
      prompt: task.prompt,
      asOf: task.asOf,
      fixtures: task.fixtures,
    },
    groundTruth: task.expected.outcome,
    expectedTrajectory: task.expected.trajectory,
    requestContext: task.requestContext,
    metadata: {
      taskId: task.id,
      taskVersion: task.taskVersion,
      schemaVersion: task.schemaVersion,
      mode: task.mode,
      suites: task.suites,
      tags: task.tags,
      budget: task.budget,
    },
  };
}
