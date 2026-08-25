import { describe, expect, it } from "vitest";

import { AUTH_SUB_KEY } from "../src/hooks/with-hooks.js";
import { permissionsApiRoutes } from "../src/permissions/api.js";
import {
  approvalInputDigest,
  PendingApprovalsStore,
  pendingApprovals,
} from "../src/permissions/pending.js";

function request(store: PendingApprovalsStore, owner = "user:alice", thread = "thread-A") {
  return store.request({
    authSub: owner,
    sessionId: thread,
    toolName: "paper.promote_candidate",
    toolInput: { candidateId: "c-42", reason: "audit" },
    approvalInput: { candidateId: "c-42" },
    timeoutMs: 5_000,
  });
}

function fakeContext(owner: string | undefined, id: string, decision: "allow" | "deny") {
  const captured = { status: 200, body: null as unknown };
  const requestContext = new Map<string, unknown>();
  if (owner) requestContext.set(AUTH_SUB_KEY, owner);
  return {
    captured,
    ctx: {
      get: (key: string) => (key === "requestContext" ? requestContext : undefined),
      req: {
        param: () => id,
        json: async () => ({ decision }),
        query: () => undefined,
      },
      json: (body: unknown, status = 200) => {
        captured.status = status;
        captured.body = body;
        return { status, body };
      },
    },
  };
}

describe("PendingApprovalsStore", () => {
  it("binds approval to owner, thread, tool and deterministic input digest", () => {
    const store = new PendingApprovalsStore(() => {});
    const view = request(store);
    expect(view.inputDigest).toBe(approvalInputDigest({ candidateId: "c-42" }));
    expect(store.list("user:bob")).toEqual([]);
    expect(store.list("user:alice")).toHaveLength(1);
    expect(store.respond(view.requestId, "allow", "user:bob")).toBe(false);
    expect(store.respond(view.requestId, "allow", "user:alice")).toBe(true);
    expect(
      store.consumeApproved({
        authSub: "user:alice",
        sessionId: "thread-B",
        toolName: "paper.promote_candidate",
        approvalInput: { candidateId: "c-42" },
      }),
    ).toBe(false);
    expect(
      store.consumeApproved({
        authSub: "user:alice",
        sessionId: "thread-A",
        toolName: "paper.promote_candidate",
        approvalInput: { candidateId: "c-42" },
      }),
    ).toBe(true);
    expect(
      store.consumeApproved({
        authSub: "user:alice",
        sessionId: "thread-A",
        toolName: "paper.promote_candidate",
        approvalInput: { candidateId: "c-42" },
      }),
    ).toBe(false);
  });

  it("deny and timeout revoke the record", async () => {
    const store = new PendingApprovalsStore(() => {});
    const denied = request(store);
    expect(store.respond(denied.requestId, "deny", "user:alice")).toBe(true);
    expect(store.size()).toBe(0);

    store.request({
      authSub: "user:alice",
      sessionId: "thread-A",
      toolName: "risk.update_config",
      toolInput: {},
      approvalInput: {},
      timeoutMs: 20,
    });
    await new Promise((resolve) => setTimeout(resolve, 40));
    expect(store.size()).toBe(0);
  });

  it("deduplicates repeated pending calls for the same approval identity", () => {
    const store = new PendingApprovalsStore(() => {});
    expect(request(store).requestId).toBe(request(store).requestId);
    expect(store.size()).toBe(1);
    store.clearAll();
  });
});

describe("permissions approval HTTP API", () => {
  const respondRoute = permissionsApiRoutes.find(
    (route) => route.path === "/permissions/:id/respond" && route.method === "POST",
  )!;

  it("requires an authenticated owner", async () => {
    pendingApprovals.clearAll();
    const view = pendingApprovals.request({
      authSub: "user:alice",
      sessionId: "thread-A",
      toolName: "paper.promote_candidate",
      toolInput: { candidateId: "c-42" },
      approvalInput: { candidateId: "c-42" },
    });
    const { ctx, captured } = fakeContext(undefined, view.requestId, "allow");
    await respondRoute.handler(ctx as never, async () => {});
    expect(captured.status).toBe(401);
    pendingApprovals.clearAll();
  });

  it("writes explicit approve only for the matching owner", async () => {
    pendingApprovals.clearAll();
    const view = pendingApprovals.request({
      authSub: "user:alice",
      sessionId: "thread-A",
      toolName: "paper.promote_candidate",
      toolInput: { candidateId: "c-42" },
      approvalInput: { candidateId: "c-42" },
    });
    const wrong = fakeContext("user:bob", view.requestId, "allow");
    await respondRoute.handler(wrong.ctx as never, async () => {});
    expect(wrong.captured.status).toBe(404);

    const matching = fakeContext("user:alice", view.requestId, "allow");
    await respondRoute.handler(matching.ctx as never, async () => {});
    expect(matching.captured.status).toBe(200);
    expect(
      pendingApprovals.consumeApproved({
        authSub: "user:alice",
        sessionId: "thread-A",
        toolName: "paper.promote_candidate",
        approvalInput: { candidateId: "c-42" },
      }),
    ).toBe(true);
  });
});
