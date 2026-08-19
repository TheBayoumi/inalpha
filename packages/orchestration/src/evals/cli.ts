import type { EvalFailureClass } from "./types.js";

/** Agent Eval CLI 的解析结果。 */
export type EvalCliArgs = {
  suite?: string;
  caseId?: string;
  trials?: string;
  report?: string;
};

/** 解析显式的成对 CLI 参数，并兼容 pnpm 透传的 `--`。 */
export function parseEvalArgs(values: string[]): EvalCliArgs {
  const parsed: Record<string, string> = {};
  const args = values.filter((value) => value !== "--");
  const names: Record<string, string> = {
    "--suite": "suite",
    "--case": "caseId",
    "--trials": "trials",
    "--report": "report",
  };
  for (let index = 0; index < args.length; index += 2) {
    const key = names[args[index] ?? ""];
    const value = args[index + 1];
    if (!key || !value) {
      throw new Error(`invalid eval argument: ${args[index] ?? ""}`);
    }
    parsed[key] = value;
  }
  return parsed;
}

/** Required lane 固定一次；live lane 只允许 3–5 次串行 trial。 */
export function parseTrialCount(
  raw: string | undefined,
  suite: string,
): number {
  const live = suite === "live";
  const value = raw === undefined ? (live ? 3 : 1) : Number(raw);
  const valid = Number.isInteger(value) && (live
    ? value >= 3 && value <= 5
    : value === 1);
  if (!valid) throw new Error("trials must be 1 offline or 3..5 live");
  return value;
}

/** 将 CLI/fixture 前置失败映射为稳定报告类别。 */
export function classifyCliFailure(error: unknown): EvalFailureClass {
  const message = error instanceof Error ? error.message : String(error);
  if (/live eval requires|not a live task/i.test(message)) return "live_provider";
  if ((error instanceof Error && error.name === "ZodError") ||
    /fixture|duplicate eval|no eval tasks|eval case not found|eval argument|trials must/i.test(message)) {
    return "fixture_invalid";
  }
  return "internal";
}