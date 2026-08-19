import { z } from "zod";

import { FixtureToolSchema, ModelTurnSchema } from "./fixture-schema.js";

export const EvalSuiteSchema = z.enum(["pr", "nightly", "live"]);

export const ResultClassSchema = z.enum([
  "success",
  "tool_error",
  "permission_deny",
  "approval_required",
  "middleware_error",
]);

const RequiredCallSchema = z
  .object({
    tool: z.string().min(1),
    inputSubset: z.record(z.string(), z.unknown()).optional(),
    result: ResultClassSchema,
  })
  .strict();

export const GoldenTaskSchema = z
  .object({
    schemaVersion: z.literal("agent-eval.v1"),
    taskVersion: z.number().int().positive(),
    id: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
    mode: z.enum(["scripted", "live"]),
    suites: z.array(EvalSuiteSchema).min(1),
    tags: z.array(z.string().min(1)),
    prompt: z.string().min(1),
    asOf: z.iso.datetime({ offset: true }),
    requestContext: z.record(z.string(), z.unknown()),
    fixtures: z
      .object({
        modelTurns: z.array(ModelTurnSchema),
        tools: z.array(FixtureToolSchema),
      })
      .strict(),
    expected: z
      .object({
        outcome: z
          .object({
            includesAll: z.array(z.string().min(1)),
            includesNone: z.array(z.string().min(1)),
          })
          .strict(),
        trajectory: z
          .object({
            requiredCalls: z.array(RequiredCallSchema),
            orderedTools: z.array(z.string().min(1)),
            forbiddenAttemptedTools: z.array(z.string().min(1)),
            forbiddenExecutedTools: z.array(z.string().min(1)),
          })
          .strict(),
      })
      .strict(),
    budget: z
      .object({
        maxSteps: z.number().int().min(1).max(40),
        maxToolCalls: z.number().int().min(0).max(100),
        timeoutMs: z.number().int().min(100).max(60_000),
      })
      .strict(),
  })
  .strict()
  .superRefine((task, ctx) => {
    const toolIds = task.fixtures.tools.map((tool) => tool.id);
    if (new Set(toolIds).size !== toolIds.length) {
      ctx.addIssue({ code: "custom", message: "duplicate id" });
    }
    const scriptedCalls = task.fixtures.modelTurns.flatMap((turn) =>
      turn.type === "tool-call" ? [turn.call] : turn.type === "tool-calls" ? turn.calls : [],
    );
    for (const call of scriptedCalls) {
      if (!toolIds.includes(call.tool)) {
        ctx.addIssue({
          code: "custom",
          message: `undeclared model tool: ${call.tool}`,
        });
      }
    }
    const expectedTools = [
      ...task.expected.trajectory.requiredCalls.map((call) => call.tool),
      ...task.expected.trajectory.orderedTools,
      ...task.expected.trajectory.forbiddenAttemptedTools,
      ...task.expected.trajectory.forbiddenExecutedTools,
    ];
    for (const tool of expectedTools) {
      if (!toolIds.includes(tool)) {
        ctx.addIssue({ code: "custom", message: `undeclared expected tool: ${tool}` });
      }
    }
    if (task.mode === "scripted") {
      const turns = task.fixtures.modelTurns;
      if (turns.length === 0 || turns.at(-1)?.type !== "text" || turns.slice(0, -1).some((turn) => turn.type === "text")) {
        ctx.addIssue({ code: "custom", message: "script requires one final text turn" });
      }
    } else {
      if (task.fixtures.modelTurns.length !== 0) {
        ctx.addIssue({ code: "custom", message: "live task has model turns" });
      }
      if (
        !task.suites.includes("live") ||
        task.suites.some((suite) => suite !== "live")
      ) {
        ctx.addIssue({ code: "custom", message: "live task must use only live suite" });
      }
    }
    if (task.mode === "scripted" && task.suites.includes("live")) {
      ctx.addIssue({ code: "custom", message: "scripted in live suite" });
    }
  });

export type GoldenTask = z.infer<typeof GoldenTaskSchema>;
export type ResultClass = z.infer<typeof ResultClassSchema>;
export type EvalSuite = z.infer<typeof EvalSuiteSchema>;
export type { ModelTurn } from "./fixture-schema.js";
