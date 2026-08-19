import type { EvalFailureClass } from "./types.js";

/** 携带稳定机器类别的评测边界错误。 */
export class EvalFailureError extends Error {
  readonly failureClass: EvalFailureClass;

  constructor(failureClass: EvalFailureClass, message: string) {
    super(message);
    this.name = "EvalFailureError";
    this.failureClass = failureClass;
  }
}

/** 优先读取结构化类别，仅为第三方异常保留文本兜底。 */
export function classifyEvalError(error: unknown): EvalFailureClass {
  if (error instanceof EvalFailureError) return error.failureClass;
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes("EVAL_NETWORK_ATTEMPT")) return "network_attempt";
  if (/tool.*schema|invalid tool input|validation error/i.test(message)) {
    return "tool_schema";
  }
  if (/scripted model|unconsumed turn/i.test(message)) return "model_protocol";
  if (/abort|timeout/i.test(message)) return "timeout";
  if (error instanceof Error && error.name === "ZodError") return "fixture_invalid";
  return "internal";
}
