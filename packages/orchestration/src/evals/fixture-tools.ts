import { createTool } from "@mastra/core/tools";
import { z } from "zod";

import type { GoldenTask } from "./schema.js";
import type { ToolExecutionEvent } from "./types.js";

/** Synthetic tools 及其原始 execute 观测。 */
export type FixtureToolSet = {
  tools: ReturnType<typeof createTool>[];
  events: ToolExecutionEvent[];
};

/**
 * 从声明式 fixture 创建无网络工具。
 *
 * 工具随后仍须经过 wireToolList；这里的事件只记录 permission/hooks 放行后是否真的
 * 进入了原始 execute，用于区分“模型尝试”和“副作用已执行”。
 */
export function createFixtureTools(task: GoldenTask): FixtureToolSet {
  const events: ToolExecutionEvent[] = [];
  const tools = task.fixtures.tools.map((fixture) =>
    createTool({
      id: fixture.id,
      description: fixture.description,
      inputSchema: z.record(z.string(), z.unknown()),
      execute: async (input, context) => {
        try {
          if (fixture.behavior.type === "throw") {
            throw new Error(fixture.behavior.message);
          }
          if (fixture.behavior.type === "delay") {
            const signal = (context as { abortSignal?: AbortSignal } | undefined)
              ?.abortSignal;
            await abortableDelay(fixture.behavior.delayMs, signal);
            events.push({ tool: fixture.id, input, status: "succeeded" });
            return fixture.behavior.value ?? null;
          }
          events.push({ tool: fixture.id, input, status: "succeeded" });
          return fixture.behavior.value;
        } catch (error) {
          events.push({ tool: fixture.id, input, status: "failed" });
          throw error;
        }
      },
    }),
  );
  return { tools, events };
}

/** 等待固定时长，并响应 Agent 的取消信号。 */
function abortableDelay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const cleanup = () => signal?.removeEventListener("abort", abort);
    const timer = setTimeout(() => {
      cleanup();
      resolve();
    }, ms);
    const abort = () => {
      clearTimeout(timer);
      cleanup();
      reject(signal?.reason ?? new Error("fixture tool aborted"));
    };
    if (signal?.aborted) {
      abort();
      return;
    }
    signal?.addEventListener("abort", abort, { once: true });
  });
}
