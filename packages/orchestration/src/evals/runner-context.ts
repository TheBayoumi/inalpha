import { RequestContext } from "@mastra/core/request-context";

import { AUTH_SUB_KEY } from "../hooks/with-hooks.js";
import type { GoldenTask } from "./schema.js";

/** 构造固定身份和 asOf 优先于 fixture 自定义字段的评测上下文。 */
export function createEvalRequestContext(
  task: GoldenTask,
): RequestContext<unknown> {
  const entries: Array<readonly [string, unknown]> = [
    ...Object.entries(task.requestContext),
    [AUTH_SUB_KEY, `eval:${task.id}`],
    ["asOf", task.asOf],
  ];
  return new RequestContext<unknown>(entries);
}
