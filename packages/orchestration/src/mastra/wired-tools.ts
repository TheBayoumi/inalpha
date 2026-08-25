import { getMcpToolsCached } from "../mcp/index.js";
import { PermissionEngine } from "../permissions/engine.js";
import { loadDefaultPermissions } from "../permissions/yaml_loader.js";
import {
  allTools,
  orchestratorToolList,
  riskTools,
  traderTools,
} from "../tools/index.js";
import {
  buildDefaultRunner,
  wireToolList,
  type WiredTool,
  type WireToolsOptions,
} from "./tool-wiring.js";

export { buildDefaultRunner, wireToolList } from "./tool-wiring.js";
export type { WiredTool, WireToolsOptions } from "./tool-wiring.js";

/** 为完整内置工具集应用默认或注入的 hooks 与权限。 */
export function wireTools(options: WireToolsOptions = {}): WiredTool[] {
  return wireToolList(allTools, options);
}

/** 生产 Agent 共享的 hook runner 与权限实例。 */
export const defaultHookRunner = buildDefaultRunner();
export const defaultPermissionEngine = new PermissionEngine(loadDefaultPermissions());

const sharedOptions: WireToolsOptions = {
  hookRunner: defaultHookRunner,
  permissionEngine: defaultPermissionEngine,
};

/** 全量 wrapped tools，保留给兼容入口。 */
export const wiredTools = wireToolList(allTools, sharedOptions);

/** Trader subagent 使用的 wrapped tools。 */
export const wiredTraderTools = wireToolList(traderTools, sharedOptions);

/** Risk subagent 使用的 wrapped tools。 */
export const wiredRiskTools = wireToolList(riskTools, sharedOptions);

/** Orchestrator 使用的 wrapped tools。 */
export const wiredOrchestratorTools = wireToolList(
  orchestratorToolList,
  sharedOptions,
);

/**
 * 加载可插拔 MCP tools，并应用与内置工具相同的 hooks 与权限。
 * MCP 全部不可用时返回空数组，不影响内置 Agent。
 */
export async function loadWiredMcpTools(): Promise<WiredTool[]> {
  const rawTools = await getMcpToolsCached();
  return rawTools.length === 0 ? [] : wireToolList(rawTools, sharedOptions);
}
