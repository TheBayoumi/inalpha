import { RequestContext } from "@mastra/core/request-context";

import { AUTH_SUB_KEY } from "../hooks/with-hooks.js";
import { createOrchestrator } from "../mastra/agents/create-orchestrator.js";
import { AskApprovalCache } from "../permissions/ask-cache.js";
import { wireToolList } from "../mastra/tool-wiring.js";
import { createFixtureTools } from "./fixture-tools.js";
import { gradeTrial } from "./grader.js";
import type { GoldenTask } from "./schema.js";
import { ScriptedModel } from "./scripted-model.js";
import { normalizeTrajectory } from "./trajectory.js";
import {
  classifyFailure,
  failedResult,
  installNetworkGuard,
  messageOf,
  numberField,
  selectFailureClass,
} from "./runner-helpers.js";
import type { EvalTrialResult, RunTrialOptions } from "./types.js";

export async function runEvalTrial(
  task: GoldenTask,
  options: RunTrialOptions,
): Promise<EvalTrialResult> {
  const started = performance.now();
  const runId = `eval:${task.id}:${options.trial}`;
  const scripted = task.mode === "scripted"
    ? new ScriptedModel(task.id, task.fixtures.modelTurns)
    : undefined;
  const model = options.model ?? scripted?.asLanguageModel();
  if (!model) return failedResult(task, options, started, "live_provider", "live model missing");

  const fixtureSet = createFixtureTools(task);
  const askCache = new AskApprovalCache(1_000, () => undefined);
  const pending = {
    request: async () => ({
      decision: "deny" as const,
      requestId: `eval-pending:${task.id}`,
      via: "timeout" as const,
    }),
  };
  const wired = wireToolList(fixtureSet.tools, {
    auditSink: () => undefined,
    askCache,
    pendingApprovals: pending,
    askTimeoutMs: 100,
  });
  const agent = createOrchestrator({
    model,
    tools: Object.fromEntries(wired.map((tool) => [tool.id, tool])),
    maxSteps: task.budget.maxSteps,
  });
  const entries: Array<readonly [string, unknown]> = [
    ...Object.entries(task.requestContext),
    [AUTH_SUB_KEY, `eval:${task.id}`],
    ["asOf", task.asOf],
  ];
  const requestContext = new RequestContext<unknown>(entries);
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(new Error("eval item timeout")),
    task.budget.timeoutMs,
  );
  const restoreFetch = installNetworkGuard(options.allowNetwork === true);

  try {
    const output = await agent.generate(task.prompt, {
      runId,
      requestContext,
      abortSignal: controller.signal,
      maxSteps: task.budget.maxSteps,
    });
    if (controller.signal.aborted) throw controller.signal.reason;
    scripted?.assertConsumed();
    const trajectory = normalizeTrajectory(output, fixtureSet.events);
    const findings = gradeTrial({
      task,
      text: output.text,
      steps: output.steps.length,
      trajectory,
    });
    const failed = findings.filter((finding) => !finding.passed);
    const failureClass = selectFailureClass(findings);
    const usage = output.totalUsage as unknown;
    return {
      taskId: task.id,
      taskVersion: task.taskVersion,
      trial: options.trial,
      passed: failed.length === 0,
      failureClass,
      findings,
      text: output.text,
      trajectory,
      metrics: {
        steps: output.steps.length,
        toolCalls: trajectory.length,
        inputTokens: numberField(usage, "inputTokens"),
        outputTokens: numberField(usage, "outputTokens"),
        totalTokens: numberField(usage, "totalTokens"),
        latencyMs: Math.round(performance.now() - started),
        costUsd: null,
      },
      model: options.modelDescriptor ?? {
        provider: scripted?.provider ?? "live",
        modelId: scripted?.modelId ?? "unknown",
      },
      runId: output.runId ?? runId,
      traceId: output.traceId ?? null,
    };
  } catch (error) {
    return failedResult(task, options, started, classifyFailure(error), messageOf(error));
  } finally {
    clearTimeout(timer);
    askCache.clear();
    restoreFetch();
  }
}
