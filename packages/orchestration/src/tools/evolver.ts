/** Evolver Mastra tools：显式发起、查询、候选详情与取消。 */
import { createTool } from "@mastra/core/tools";
import { z } from "zod";

import {
  evolutionConfigSchema,
  getApprovedEvolutionRunContext,
  getEvolverClient,
  type ToolRequestContext,
} from "./evolver-shared.js";

export const evolverRunEvolutionTool = createTool({
  id: "evolver.run_evolution",
  description: `
启动一次真实数据驱动的单代策略演化。每个候选经过源码审计、契约校验和同一冻结数据集回测；调用会产生 LLM 与计算成本，必须获得用户确认。
何时用：用户明确要求变异、优化或探索已存在策略的新方向。
何时不用：只需一次回测时用 paper.run_backtest；种子未验证或用户未授权额外成本时不要调用。
坑：返回 queued run_id 后用 evolver.get_evolution 轮询；freshness 不足会 fail closed；不会自动 promote、注册或启动候选。
  `.trim(),
  inputSchema: z.object({
    budget: z.number().int().min(1).max(20).default(4),
    seedStrategyId: z.string().min(1).max(128).default("sma_cross_v1"),
    config: evolutionConfigSchema,
  }),
  execute: async (inputData, ctx) => {
    const approved = await getApprovedEvolutionRunContext(
      inputData,
      ctx?.requestContext as ToolRequestContext | undefined,
    );
    return await approved.client.startRun({
      request: approved.request,
      idempotencyKey: approved.operationId,
      credentialGrant: approved.credentialGrant,
    });
  },
});

export const evolverGetEvolutionTool = createTool({
  id: "evolver.get_evolution",
  description: `
查询演化 run 的状态、数据 manifest 和已完成 slot。
何时用：轮询 queued/running/cancelling run，或复核 completed/failed/aborted 历史。
何时不用：只看单个候选完整源码和 diff 时用 evolver.get_candidate。
坑：跨用户资源统一返回 404；terminal 状态无需继续轮询。
  `.trim(),
  inputSchema: z.object({ runId: z.string().uuid() }),
  execute: async (inputData, ctx) =>
    await (await getEvolverClient(ctx?.requestContext as ToolRequestContext | undefined)).getRun(inputData.runId),
});

export const evolverGetCandidateTool = createTool({
  id: "evolver.get_candidate",
  description: "查询当前用户拥有的单个演化候选源码、diff、审计与真实回测快照；不用它列 run。",
  inputSchema: z.object({ candidateId: z.string().uuid() }),
  execute: async (inputData, ctx) =>
    await (await getEvolverClient(ctx?.requestContext as ToolRequestContext | undefined)).getCandidate(inputData.candidateId),
});

export const evolverAbortEvolutionTool = createTool({
  id: "evolver.abort_evolution",
  description: "取消 queued/running 演化 run；保留已完成 slot。仅在用户明确要求停止时使用，terminal run 无需调用。",
  inputSchema: z.object({ runId: z.string().uuid() }),
  execute: async (inputData, ctx) =>
    await (await getEvolverClient(ctx?.requestContext as ToolRequestContext | undefined)).abortRun(inputData.runId),
});

export const evolverTools = [
  evolverRunEvolutionTool,
  evolverGetEvolutionTool,
  evolverGetCandidateTool,
  evolverAbortEvolutionTool,
] as const;
