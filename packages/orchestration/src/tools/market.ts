/**
 * 市场级行情归因 tool（D-12+）—— services/data 的 /market/* 端点包装。
 *
 * 行情归因（"今天为什么涨/跌"）的四个数据维度，全部无需 symbol。
 * venue 按 market 参数路由：新闻支持全部已声明市场；板块、资金与强势股当前仅支持
 * cn（A股，直连东财/同花顺，配方源自 a-stock-data）。
 *
 * Tool 设计遵循 docs/05-tool-skill-discipline.md：description 四要素。
 */
import { createTool } from "@mastra/core/tools";
import { z } from "zod";

import { resolveRequestToken } from "../auth.js";
import { DataClient } from "../clients/data.js";
import { getSettings } from "../config.js";

type ToolRequestContext = { authToken?: string; get?: (key: string) => unknown };

async function getClient(ctx?: ToolRequestContext): Promise<DataClient> {
  const settings = getSettings();
  const token = await resolveRequestToken(ctx);
  return new DataClient({ baseUrl: settings.dataServiceUrl, token });
}

const NewsMarketSchema = z.enum([
  "cn", "us", "hk", "jp", "kr", "au", "in", "uk",
  "de", "fr", "ca", "br", "global", "crypto",
]).default("cn")
  .describe("市场；A股走东财，Crypto 走财经 feed，其余股票市场走明确标注的代表指数/ETF 新闻代理");

const CnMarketSchema = z.enum(["cn"]).default("cn")
  .describe("市场；当前仅支持 cn（A股）");

// ────────────────────────────────────────────────────────────────────
// data.get_market_news
// ────────────────────────────────────────────────────────────────────

export const dataGetMarketNewsTool = createTool({
  id: "data.get_market_news",
  description: `
    多市场财经快讯流，**无需 symbol**。A股走东财，Crypto 走专业财经 feed；其他
    股票市场走代表性指数/ETF 的 Yahoo 新闻代理，条目会保留代理 ticker 与口径声明。
    响应含逐 provider status、UTC 时间戳与部分失败标志。

    何时用：
    - 行情归因："某市场 / 大盘今天为什么涨跌、有什么消息"——**优先于 web.search_news**
      （专业财经快讯源，免搜索引擎噪声、免中文新闻无源问题）
    - 盘面突发：用户问"刚刚发生了什么"级别的即时动态

    何时不用：
    - 股票单标的新闻 / 官方披露 → data.get_news，返回 URL 再用 web.fetch 读原文；
      只有无覆盖或 provider 故障才降级 web.search_news
    - Crypto 单币种新闻 → web.search_news（已注册 feed 只有市场级覆盖）
    - 历史新闻回溯 → 快讯流只有最近一段，不是新闻库

    坑：
    - published_at 已转 UTC；引用时按 §3.1 标注数据时点
    - 60s 进程内缓存；快讯≠结论，结论级引用先 web.fetch 读原文
    - A股源站故障返回 error 字段（502 MARKET_DATA_UNAVAILABLE）；其它市场通过
      providers[].status / is_partial 表示部分或全部来源故障。此时降级 web.search_news
      并显式说明结构化快讯源不可用
  `.trim(),
  inputSchema: z.object({
    market: NewsMarketSchema,
    limit: z.number().int().min(1).max(50).default(20),
  }),
  execute: async (inputData, ctx) => {
    const tc = ctx?.requestContext as ToolRequestContext | undefined;
    const client = await getClient(tc);
    return await client.getMarketNews({
      market: inputData.market ?? "cn",
      limit: inputData.limit ?? 20,
    });
  },
});

// ────────────────────────────────────────────────────────────────────
// data.get_market_sectors
// ────────────────────────────────────────────────────────────────────

export const dataGetMarketSectorsTool = createTool({
  id: "data.get_market_sectors",
  description: `
    行业板块涨跌幅榜（A股=东财 ~500 个行业板块，涨跌两端各 top_n），含每板块
    涨跌家数 + 领涨股。

    何时用：
    - 行情归因第一步：判断"普涨还是结构性"（top 与 bottom 的涨跌幅分布）、
      哪些板块在带动指数
    - 找当日主线后下钻：领涨板块的 leader 股可用 data.search_symbol 解析再深挖

    何时不用：
    - 单一标的行情 → data.get_bars / data.get_ticker
    - 板块历史走势回测 → 因子 / 回测链路，本 tool 只有当日快照

    坑：
    - pct_chg 是百分数（3.5 = +3.5%）；fetched_at 为拉取时刻，盘后调用拿的是收盘快照
    - 60s 缓存；不要循环逐板块调用
  `.trim(),
  inputSchema: z.object({
    market: CnMarketSchema,
    topN: z.number().int().min(1).max(50).default(10),
  }),
  execute: async (inputData, ctx) => {
    const tc = ctx?.requestContext as ToolRequestContext | undefined;
    const client = await getClient(tc);
    return await client.getMarketSectors({
      market: inputData.market ?? "cn",
      topN: inputData.topN ?? 10,
    });
  },
});

// ────────────────────────────────────────────────────────────────────
// data.get_market_moneyflow
// ────────────────────────────────────────────────────────────────────

export const dataGetMarketMoneyflowTool = createTool({
  id: "data.get_market_moneyflow",
  description: `
    跨境资金流向（A股=沪深港通分钟级累计净买入，亿元，负=净流出），含日内
    ~30 分钟间隔采样曲线。

    何时用：
    - 行情归因的资金面维度：当日大涨/大跌是否伴随北向/南向异动
    - 判断"外资在买还是在卖"的方向性问题

    何时不用：
    - 个股资金流 / 主力净流入 → 暂无工具，不要拿全市场数据冒充个股结论
    - 历史资金流统计 → 本 tool 只有当日曲线

    坑：
    - **数值是同花顺估算口径**：交易所 2024-08 起不再盘中披露北向官方数据——
      引用时必须带"估算口径"声明（响应 note 字段已写明），只用于方向判断
    - as_of_time 是北京时间 HH:MM；非交易时段拿的是上一交易日尾盘值
  `.trim(),
  inputSchema: z.object({
    market: CnMarketSchema,
  }),
  execute: async (inputData, ctx) => {
    const tc = ctx?.requestContext as ToolRequestContext | undefined;
    const client = await getClient(tc);
    return await client.getMarketMoneyflow({ market: inputData.market ?? "cn" });
  },
});

// ────────────────────────────────────────────────────────────────────
// data.get_market_movers
// ────────────────────────────────────────────────────────────────────

export const dataGetMarketMoversTool = createTool({
  id: "data.get_market_movers",
  description: `
    当日强势股 + 人工题材标签（A股=同花顺，reason 如"绿色算力+矿业"已拆成 tags）。
    归因"今天什么主线在涨"的最直接结构化证据——对 tags 聚类即可看出当日热点题材。

    何时用：
    - 行情归因的题材维度：大涨日看强势股题材聚类，判断主线（与板块榜互证）
    - 用户问"今天什么题材 / 概念在炒"

    何时不用：
    - 选股 / 买卖决策——强势≠值得追，落子仍归 research / factor / 风控链路
    - 非 A股市场（未实装）

    坑：
    - 题材标签是媒体/数据商人工归纳，**非因果实锤**——引用措辞用"市场归因于 /
      题材标签显示"，不要写成"因为 X 所以涨"
    - 含 ST / 涨停板个股，标签可能滞后；60s 缓存
  `.trim(),
  inputSchema: z.object({
    market: CnMarketSchema,
    limit: z.number().int().min(1).max(50).default(30),
  }),
  execute: async (inputData, ctx) => {
    const tc = ctx?.requestContext as ToolRequestContext | undefined;
    const client = await getClient(tc);
    return await client.getMarketMovers({
      market: inputData.market ?? "cn",
      limit: inputData.limit ?? 30,
    });
  },
});

export const marketTools = [
  dataGetMarketNewsTool,
  dataGetMarketSectorsTool,
  dataGetMarketMoneyflowTool,
  dataGetMarketMoversTool,
] as const;
