/** 创建可按字段覆盖的完整 Golden Task 测试输入。 */
export function makeValidGoldenTask(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    schemaVersion: "agent-eval.v1",
    taskVersion: 1,
    id: "valid-task",
    mode: "scripted",
    suites: ["pr"],
    tags: [],
    prompt: "test",
    asOf: "2026-08-18T09:00:00Z",
    requestContext: {},
    fixtures: {
      modelTurns: [{ type: "text", text: "done" }],
      tools: [],
    },
    expected: {
      outcome: { includesAll: [], includesNone: [] },
      trajectory: {
        requiredCalls: [],
        orderedTools: [],
        forbiddenAttemptedTools: [],
        forbiddenExecutedTools: [],
      },
    },
    budget: { maxSteps: 2, maxToolCalls: 0, timeoutMs: 1000 },
    ...overrides,
  };
}
