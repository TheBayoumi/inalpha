import type { LanguageModel } from "@mastra/core/llm";

import type { GoldenTask, ResultClass } from "./schema.js";

/** 单次 trial 的可选真实模型配置。 */
export type RunTrialOptions = {
  trial: number;
  model?: LanguageModel;
  modelDescriptor?: { provider: string; modelId: string };
  allowNetwork?: boolean;
};

/** Synthetic tool 原始 execute 的观测事件。 */
export type ToolExecutionEvent = {
  tool: string;
  input: unknown;
  status: "succeeded" | "failed";
};

/** 从 Mastra step 规范化得到的一次工具调用。 */
export type NormalizedToolCall = {
  index: number;
  step: number;
  tool: string;
  input: unknown;
  result: unknown;
  resultClass: ResultClass;
  attempted: true;
  executed: boolean;
};

/** 稳定的评测失败类别。 */
export type EvalFailureClass =
  | "fixture_invalid"
  | "model_protocol"
  | "tool_schema"
  | "permission_violation"
  | "trajectory_mismatch"
  | "outcome_mismatch"
  | "step_budget"
  | "timeout"
  | "network_attempt"
  | "live_provider"
  | "internal";

/** 单个确定性断言的结果。 */
export type GradeFinding = {
  passed: boolean;
  failureClass?: EvalFailureClass;
  message: string;
};

/** 单次 case trial 的完整结果。 */
export type EvalTrialResult = {
  taskId: string;
  taskVersion: number;
  trial: number;
  passed: boolean;
  failureClass: EvalFailureClass | null;
  findings: GradeFinding[];
  text: string;
  trajectory: NormalizedToolCall[];
  metrics: {
    steps: number;
    toolCalls: number;
    inputTokens: number | null;
    outputTokens: number | null;
    totalTokens: number | null;
    latencyMs: number;
    costUsd: null;
  };
  model: {
    provider: string;
    modelId: string;
  };
  runId: string | null;
  traceId: string | null;
};

/** Runner 内部传给 grader 的数据。 */
export type GradeInput = {
  task: GoldenTask;
  text: string;
  steps: number;
  trajectory: NormalizedToolCall[];
};

/** 同一 task 多次 trial 的稳定统计。 */
export type EvalTaskSummary = {
  taskId: string;
  trials: number;
  passedCount: number;
  passRate: number;
  latencyMeanMs: number;
  latencyVarianceMs2: number;
  totalTokensMean: number | null;
  totalTokensVariance: number | null;
};

/** Suite 在 task 执行前发生的结构化失败。 */
export type EvalSuiteError = {
  failureClass: EvalFailureClass;
  message: string;
};

/** 一个 suite 的机器可读报告。 */
export type EvalSuiteReport = {
  schemaVersion: "agent-eval-report.v1";
  suite: string;
  passed: boolean;
  total: number;
  passedCount: number;
  failedCount: number;
  errors: EvalSuiteError[];
  taskSummaries: EvalTaskSummary[];
  results: EvalTrialResult[];
};
