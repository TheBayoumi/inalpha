import { describe, expect, it, vi } from "vitest";

import { AUTH_SUB_KEY, HookRunner, withHooks } from "../src/hooks/index.js";
import {
  APPROVAL_OPERATION_ID_KEY,
  buildEvolutionLLMSnapshot,
  USER_LLM_SNAPSHOT_KEY,
} from "../src/mastra/llm/evolution-snapshot.js";
import { PendingApprovalsStore } from "../src/permissions/pending.js";

function toolContext(owner: string, thread: string, runId = "turn-1") {
  const requestContext = new Map<string, unknown>();
  requestContext.set(AUTH_SUB_KEY, owner);
  return { requestContext, agent: { threadId: thread }, runId };
}

function makeApprovalTool(timeoutMs = 5_000) {
  const events: Array<Record<string, unknown>> = [];
  const store = new PendingApprovalsStore((event) => events.push(event));
  const execute = vi.fn().mockResolvedValue({ status: "executed" });
  const wrapped = withHooks(
    { id: "paper.promote_candidate", execute },
    {
      runner: new HookRunner(),
      permissionResolver: () => "ask",
      pendingApprovals: store,
      askTimeoutMs: timeoutMs,
    },
  );
  return { events, store, execute, wrapped };
}

describe("explicit approval path", () => {
  it("pending、无关新 turn 和拒绝都不会执行", async () => {
    const { store, execute, wrapped } = makeApprovalTool();
    const input = { candidateId: "c-42", reason: "first" };
    const first = (await wrapped.execute!(input, toolContext("user:alice", "thread-A"))) as {
      requestId: string;
    };

    await wrapped.execute!(input, toolContext("user:alice", "thread-A", "turn-2"));
    expect(execute).not.toHaveBeenCalled();
    expect(store.respond(first.requestId, "deny", "user:alice")).toBe(true);
    await wrapped.execute!(input, toolContext("user:alice", "thread-A", "turn-3"));
    expect(execute).not.toHaveBeenCalled();
    store.clearAll();
  });

  it("显式 approve 后只执行一次，二次重放失败", async () => {
    const { store, execute, wrapped } = makeApprovalTool();
    const first = (await wrapped.execute!(
      { candidateId: "c-42", reason: "first wording" },
      toolContext("user:alice", "thread-A"),
    )) as { requestId: string };

    expect(store.respond(first.requestId, "allow", "user:alice")).toBe(true);
    const approved = await wrapped.execute!(
      { candidateId: "c-42", reason: "changed audit wording" },
      toolContext("user:alice", "thread-A", "turn-2"),
    );
    expect(approved).toEqual({ status: "executed" });
    expect(execute).toHaveBeenCalledOnce();

    const replay = (await wrapped.execute!(
      { candidateId: "c-42", reason: "third wording" },
      toolContext("user:alice", "thread-A", "turn-3"),
    )) as { requiresApproval: boolean };
    expect(replay.requiresApproval).toBe(true);
    expect(execute).toHaveBeenCalledOnce();
    store.clearAll();
  });

  it("不同 owner 或 thread 不能消费批准", async () => {
    const { store, execute, wrapped } = makeApprovalTool();
    const first = (await wrapped.execute!(
      { candidateId: "c-42" },
      toolContext("user:alice", "thread-A"),
    )) as { requestId: string };
    expect(store.respond(first.requestId, "allow", "user:bob")).toBe(false);
    expect(store.respond(first.requestId, "allow", "user:alice")).toBe(true);

    await wrapped.execute!({ candidateId: "c-42" }, toolContext("user:alice", "thread-B"));
    await wrapped.execute!({ candidateId: "c-42" }, toolContext("user:bob", "thread-A"));
    expect(execute).not.toHaveBeenCalled();

    await wrapped.execute!({ candidateId: "c-42" }, toolContext("user:alice", "thread-A"));
    expect(execute).toHaveBeenCalledOnce();
    store.clearAll();
  });

  it("timeout 撤销批准，后续调用不执行", async () => {
    const { store, execute, wrapped } = makeApprovalTool(30);
    const first = (await wrapped.execute!(
      { candidateId: "c-42" },
      toolContext("user:alice", "thread-A"),
    )) as { requestId: string };
    expect(store.respond(first.requestId, "allow", "user:alice")).toBe(true);
    await new Promise((resolve) => setTimeout(resolve, 60));

    await wrapped.execute!({ candidateId: "c-42" }, toolContext("user:alice", "thread-A"));
    expect(execute).not.toHaveBeenCalled();
    store.clearAll();
  });

  it("缺 owner 或稳定 thread 时 fail closed 且不创建全局审批", async () => {
    const { store, execute, wrapped } = makeApprovalTool();
    const noOwner = (await wrapped.execute!(
      { candidateId: "c-42" },
      { agent: { threadId: "thread-A" }, runId: "turn-1" },
    )) as { message: string };
    const requestContext = new Map<string, unknown>([[AUTH_SUB_KEY, "user:alice"]]);
    const noThread = (await wrapped.execute!(
      { candidateId: "c-42" },
      { requestContext, runId: "turn-2" },
    )) as { message: string };

    expect(noOwner.message).toContain("verified owner");
    expect(noThread.message).toContain("stable thread/session");
    expect(store.size()).toBe(0);
    expect(execute).not.toHaveBeenCalled();
  });

  it("演化审批冻结 LLM 快照，并在响应丢失后的同范围调用中复用 operation ID", async () => {
    const store = new PendingApprovalsStore(() => {});
    const observedOperations: unknown[] = [];
    const execute = vi.fn().mockImplementation((_input, context) => {
      observedOperations.push(context.requestContext.get(APPROVAL_OPERATION_ID_KEY));
      return { status: "executed" };
    });
    const wrapped = withHooks(
      { id: "evolver.run_evolution", execute },
      {
        runner: new HookRunner(),
        permissionResolver: () => "ask",
        pendingApprovals: store,
        askTimeoutMs: 5_000,
      },
    );
    const input = { budget: 1, config: { symbol: "BTCUSDT" } };
    const context = toolContext("user:alice", "thread-A");
    context.requestContext.set(
      USER_LLM_SNAPSHOT_KEY,
      buildEvolutionLLMSnapshot({
        id: "config-1",
        provider: "deepseek",
        api_key: "must-not-enter-approval",
      }),
    );

    const pending = (await wrapped.execute!(input, context)) as {
      requestId: string;
      toolInput: unknown;
    };
    expect(JSON.stringify(pending.toolInput)).not.toContain("must-not-enter-approval");
    expect(store.respond(pending.requestId, "allow", "user:alice")).toBe(true);

    expect(await wrapped.execute!(input, context)).toEqual({ status: "executed" });
    expect(await wrapped.execute!(input, context)).toEqual({ status: "executed" });
    expect(observedOperations).toEqual([pending.requestId, pending.requestId]);
    store.clearAll();
  });
});
