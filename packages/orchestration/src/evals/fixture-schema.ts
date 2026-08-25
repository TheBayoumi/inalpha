import { z } from "zod";

const ToolCallSchema = z
  .object({
    tool: z.string().min(1),
    input: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();

/** Scripted model 的一次确定性输出。 */
export const ModelTurnSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("text"), text: z.string() }).strict(),
  z.object({ type: z.literal("tool-call"), call: ToolCallSchema }).strict(),
  z
    .object({
      type: z.literal("tool-calls"),
      calls: z.array(ToolCallSchema).min(1),
    })
    .strict(),
]);

const ToolBehaviorSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("return"), value: z.unknown() }).strict(),
  z.object({ type: z.literal("throw"), message: z.string().min(1) }).strict(),
  z
    .object({
      type: z.literal("delay"),
      delayMs: z.number().int().positive(),
      value: z.unknown().optional(),
    })
    .strict(),
]);

/** 无网络 synthetic tool 的声明式 fixture。 */
export const FixtureToolSchema = z
  .object({
    id: z.string().min(1),
    description: z.string().min(1),
    behavior: ToolBehaviorSchema,
  })
  .strict();

export type ModelTurn = z.infer<typeof ModelTurnSchema>;
