/** Evolver Mastra tools 的共享 schema 与客户端解析。 */
import { z } from "zod";

import { resolveRequestToken } from "../auth.js";
import { EvolverClient } from "../clients/evolver.js";
import { getSettings } from "../config.js";

export type ToolRequestContext = { authToken?: string; get?: (key: string) => unknown };

export async function getEvolverClient(ctx?: ToolRequestContext): Promise<EvolverClient> {
  return new EvolverClient({
    baseUrl: getSettings().evolverServiceUrl,
    token: await resolveRequestToken(ctx),
    timeoutMs: 30_000,
  });
}

export const evolutionConfigSchema = z.object({
  venue: z.string().min(1).describe("数据 venue；按标的市场选择，不预设市场"),
  symbol: z.string().min(1).describe("该 venue 使用的标的代码"),
  timeframe: z.enum([
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
    "6h", "8h", "12h", "1d", "3d", "1wk", "1mo",
  ]),
  from_ts: z.string().datetime().describe("评估窗口起点，ISO-8601 UTC"),
  as_of: z.string().datetime().describe("真实当前评估时点，ISO-8601 UTC"),
  initial_cash: z.number().min(100).default(10_000),
  fee_rate: z.number().min(0).max(0.1).default(0.001),
  validation_split: z.number().min(0).max(0.5).default(0.3),
});
