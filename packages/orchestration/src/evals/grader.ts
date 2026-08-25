import type { GradeFinding, GradeInput, NormalizedToolCall } from "./types.js";

/** 对一次 Agent trial 执行全部确定性断言。 */
export function gradeTrial(input: GradeInput): GradeFinding[] {
  return [
    ...gradeRequiredCalls(input),
    gradeOrderedTools(input),
    gradeForbiddenAttempts(input),
    gradeForbiddenExecutions(input),
    gradeBudgets(input),
    gradeOutcome(input),
  ];
}

function gradeRequiredCalls(input: GradeInput): GradeFinding[] {
  const used = new Set<number>();
  return input.task.expected.trajectory.requiredCalls.map((expected) => {
    const match = input.trajectory.find(
      (call) =>
        !used.has(call.index) &&
        call.tool === expected.tool &&
        call.resultClass === expected.result &&
        (expected.inputSubset === undefined || deepSubset(call.input, expected.inputSubset)),
    );
    if (match) used.add(match.index);
    return {
      passed: Boolean(match),
      failureClass: match ? undefined : "trajectory_mismatch",
      message: match
        ? `required call matched: ${expected.tool}`
        : `required call missing: ${expected.tool}`,
    };
  });
}

function gradeOrderedTools(input: GradeInput): GradeFinding {
  const expected = input.task.expected.trajectory.orderedTools;
  let cursor = 0;
  for (const call of input.trajectory) {
    if (call.tool === expected[cursor]) cursor += 1;
  }
  const passed = cursor === expected.length;
  return finding(passed, "trajectory_mismatch", "ordered tool subsequence");
}

function gradeForbiddenAttempts(input: GradeInput): GradeFinding {
  const forbidden = new Set(input.task.expected.trajectory.forbiddenAttemptedTools);
  const hit = input.trajectory.find((call) => forbidden.has(call.tool));
  return finding(!hit, "trajectory_mismatch", `forbidden attempt${hit ? `: ${hit.tool}` : ""}`);
}

function gradeForbiddenExecutions(input: GradeInput): GradeFinding {
  const forbidden = new Set(input.task.expected.trajectory.forbiddenExecutedTools);
  const hit = input.trajectory.find((call) => call.executed && forbidden.has(call.tool));
  return finding(!hit, "permission_violation", `forbidden execution${hit ? `: ${hit.tool}` : ""}`);
}

function gradeBudgets(input: GradeInput): GradeFinding {
  const { maxSteps, maxToolCalls } = input.task.budget;
  const passed = input.steps <= maxSteps && input.trajectory.length <= maxToolCalls;
  return finding(
    passed,
    "step_budget",
    `budget steps=${input.steps}/${maxSteps}, calls=${input.trajectory.length}/${maxToolCalls}`,
  );
}

function gradeOutcome(input: GradeInput): GradeFinding {
  const text = input.text.toLowerCase();
  const { includesAll, includesNone } = input.task.expected.outcome;
  const missing = includesAll.filter((value) => !text.includes(value.toLowerCase()));
  const forbidden = includesNone.filter((value) => text.includes(value.toLowerCase()));
  const passed = missing.length === 0 && forbidden.length === 0;
  return finding(
    passed,
    "outcome_mismatch",
    `outcome missing=${JSON.stringify(missing)}, forbidden=${JSON.stringify(forbidden)}`,
  );
}

function finding(
  passed: boolean,
  failureClass: GradeFinding["failureClass"],
  message: string,
): GradeFinding {
  return { passed, failureClass: passed ? undefined : failureClass, message };
}

/** 判断 actual 是否递归包含 expected 的全部字段。 */
export function deepSubset(actual: unknown, expected: unknown): boolean {
  if (Object.is(actual, expected)) return true;
  if (Array.isArray(expected)) {
    return Array.isArray(actual) &&
      expected.length <= actual.length &&
      expected.every((value, index) => deepSubset(actual[index], value));
  }
  if (!expected || typeof expected !== "object") return false;
  if (!actual || typeof actual !== "object" || Array.isArray(actual)) return false;
  return Object.entries(expected as Record<string, unknown>).every(([key, value]) =>
    deepSubset((actual as Record<string, unknown>)[key], value),
  );
}
