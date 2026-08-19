import {
  defaultAuditRegistration,
} from "../hooks/handlers/audit-log.js";
import { defaultEvolutionOnPromoteRegistration } from "../hooks/handlers/evolution-on-promote.js";
import { defaultFactorExpressionAuditRegistration } from "../hooks/handlers/factor-expression-audit.js";
import { defaultGridSizeCapRegistration } from "../hooks/handlers/grid-size-cap.js";
import { defaultIdempotencyRegistrations } from "../hooks/handlers/tool-idempotency.js";
import { defaultInjectCurrentDateRegistration } from "../hooks/handlers/inject-current-date.js";
import { defaultStrategyCodeAuditRegistration } from "../hooks/handlers/strategy-code-audit.js";
import { HookRunner } from "../hooks/runner.js";
import { withHooks, type PendingApprovalsLike } from "../hooks/with-hooks.js";
import type { AskApprovalCache } from "../permissions/ask-cache.js";
import { PermissionEngine } from "../permissions/engine.js";
import type { Decision } from "../permissions/types.js";
import { loadDefaultPermissions } from "../permissions/yaml_loader.js";

/** 通用 tool wiring 的可注入依赖。 */
export type WireToolsOptions = {
  hookRunner?: HookRunner;
  permissionEngine?: PermissionEngine;
  auditSink?: (record: Record<string, unknown>) => void;
  pendingApprovals?: PendingApprovalsLike;
  askTimeoutMs?: number;
  askCache?: AskApprovalCache;
};

/** hooks + permissions 包装后的宽松 tool 形态。 */
export type WiredTool = {
  id: string;
  description?: string;
  execute?: (input: unknown, ctx?: unknown) => Promise<unknown> | unknown;
  [key: string]: unknown;
};

/** 创建每次调用隔离的默认 hook runner。 */
export function buildDefaultRunner(
  auditSink?: (record: Record<string, unknown>) => void,
): HookRunner {
  const runner = new HookRunner();
  runner.register(defaultAuditRegistration(auditSink));
  runner.register(defaultGridSizeCapRegistration());
  runner.register(defaultInjectCurrentDateRegistration());
  runner.register(defaultStrategyCodeAuditRegistration());
  runner.register(defaultFactorExpressionAuditRegistration());
  runner.register(defaultEvolutionOnPromoteRegistration());
  const idempotency = defaultIdempotencyRegistrations();
  runner.register(idempotency.pre);
  runner.register(idempotency.post);
  return runner;
}

/** 把任意 tool 子集套上真实 hooks 与 permission engine。 */
export function wireToolList(
  tools: readonly unknown[],
  options: WireToolsOptions = {},
): WiredTool[] {
  const runner = options.hookRunner ?? buildDefaultRunner(options.auditSink);
  const engine =
    options.permissionEngine ?? new PermissionEngine(loadDefaultPermissions());
  const resolver = (toolName: string, input: unknown): Decision =>
    engine.authorize(toolName, input).decision;
  return tools.map((tool) =>
    withHooks(tool as WiredTool, {
      runner,
      permissionResolver: resolver,
      pendingApprovals: options.pendingApprovals,
      askTimeoutMs: options.askTimeoutMs,
      askCache: options.askCache,
    }),
  );
}
