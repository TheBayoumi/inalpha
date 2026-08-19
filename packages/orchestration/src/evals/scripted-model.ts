import type { LanguageModel } from "@mastra/core/llm";

import type { ModelTurn } from "./schema.js";

const USAGE = { inputTokens: 1, outputTokens: 1, totalTokens: 2 };

type Generated = {
  content: Record<string, unknown>[];
  finishReason: "stop" | "tool-calls";
  usage: typeof USAGE;
  warnings: never[];
  response: { id: string; modelId: string; timestamp: Date };
};

/** 严格按声明式 turns 响应的离线 AI SDK v2 model。 */
export class ScriptedModel {
  readonly provider = "scripted-eval";
  readonly modelId: string;
  readonly specificationVersion = "v2" as const;
  readonly supportedUrls = {};
  readonly calls: unknown[] = [];
  private cursor = 0;

  constructor(
    modelId: string,
    private readonly turns: readonly ModelTurn[],
  ) {
    this.modelId = modelId;
  }

  /** 返回可传给 Mastra Agent 的模型边界。 */
  asLanguageModel(): LanguageModel {
    return this as unknown as LanguageModel;
  }

  /** 生成下一段确定性输出；额外调用会立即失败。 */
  async doGenerate(options: unknown): Promise<Generated> {
    this.calls.push(options);
    return this.next();
  }

  /** 以 AI SDK v2 chunk 协议流式返回同一确定性输出。 */
  async doStream(options: unknown): Promise<{ stream: ReadableStream<unknown> }> {
    this.calls.push(options);
    const generated = this.next();
    return { stream: streamGenerated(generated) };
  }

  /** 确保 Agent 没有提前结束并遗留 scripted turn。 */
  assertConsumed(): void {
    if (this.cursor !== this.turns.length) {
      throw new Error(`script has ${this.turns.length - this.cursor} unconsumed turn(s)`);
    }
  }

  private next(): Generated {
    const turn = this.turns[this.cursor];
    if (!turn) throw new Error("scripted model received an unexpected extra call");
    const turnIndex = this.cursor++;
    const content = turnContent(turn, turnIndex);
    return {
      content,
      finishReason: turn.type === "text" ? "stop" : "tool-calls",
      usage: USAGE,
      warnings: [],
      response: {
        id: `eval-response-${turnIndex}`,
        modelId: this.modelId,
        timestamp: new Date(0),
      },
    };
  }
}

function turnContent(turn: ModelTurn, turnIndex: number): Record<string, unknown>[] {
  if (turn.type === "text") return [{ type: "text", text: turn.text }];
  const calls = turn.type === "tool-call" ? [turn.call] : turn.calls;
  return calls.map((call, callIndex) => ({
    type: "tool-call",
    toolCallId: `eval-call-${turnIndex}-${callIndex}`,
    toolName: call.tool,
    input: JSON.stringify(call.input),
  }));
}

function streamGenerated(generated: Generated): ReadableStream<unknown> {
  return new ReadableStream({
    start(controller) {
      controller.enqueue({ type: "stream-start", warnings: [] });
      controller.enqueue({ type: "response-metadata", ...generated.response });
      for (const part of generated.content) enqueuePart(controller, part);
      controller.enqueue({
        type: "finish",
        finishReason: generated.finishReason,
        usage: generated.usage,
      });
      controller.close();
    },
  });
}

function enqueuePart(
  controller: ReadableStreamDefaultController<unknown>,
  part: Record<string, unknown>,
): void {
  if (part.type === "tool-call") {
    const id = String(part.toolCallId);
    controller.enqueue({ type: "tool-input-start", id, toolName: part.toolName });
    controller.enqueue({ type: "tool-input-delta", id, delta: part.input });
    controller.enqueue({ type: "tool-input-end", id });
    controller.enqueue(part);
    return;
  }
  const id = "eval-text";
  controller.enqueue({ type: "text-start", id });
  controller.enqueue({ type: "text-delta", id, delta: part.text });
  controller.enqueue({ type: "text-end", id });
}
