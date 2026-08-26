import { createHash, randomUUID } from "node:crypto";

import { insertPending, markResolved } from "./repo.js";

export type PendingDecision = "allow" | "deny";

export interface PendingApprovalView {
  requestId: string;
  toolName: string;
  toolInput: unknown;
  sessionId: string;
  inputDigest: string;
  createdAt: string;
  deadline: string;
}

export interface PendingRequestArgs {
  toolName: string;
  toolInput: unknown;
  approvalInput: unknown;
  sessionId: string;
  authSub: string;
  timeoutMs?: number;
}

export interface PendingConsumeArgs {
  toolName: string;
  approvalInput: unknown;
  sessionId: string;
  authSub: string;
  reuseAfterConsume?: boolean;
}

interface PendingApprovalRecord extends PendingApprovalView {
  authSub: string;
  status: "pending" | "approved";
  timer: ReturnType<typeof setTimeout>;
}

interface ConsumedApprovalRecord {
  operationId: string;
  deadline: string;
  timer: ReturnType<typeof setTimeout>;
}

const DEFAULT_TIMEOUT_MS = 30_000;

export type PendingTelemetrySink = (record: Record<string, unknown>) => void;

const defaultPendingTelemetrySink: PendingTelemetrySink = (record) => {
  console.log(JSON.stringify(record));
};

export interface ApprovalPersistence {
  insertPending(view: PendingApprovalView, authSub?: string): Promise<void>;
  markResolved(
    requestId: string,
    decision: PendingDecision,
    via: "user" | "timeout",
  ): Promise<void>;
}

/** Produces a deterministic SHA-256 digest for an approval-defining input. */
export function approvalInputDigest(input: unknown): string {
  return createHash("sha256").update(stableStringify(input)).digest("hex");
}

/** Stores pending and approved decisions until one matching tool call consumes them. */
export class PendingApprovalsStore {
  private readonly records = new Map<string, PendingApprovalRecord>();
  private readonly identityIndex = new Map<string, string>();
  private readonly consumedByIdentity = new Map<string, ConsumedApprovalRecord>();
  private readonly telemetry: PendingTelemetrySink;
  private readonly persistence?: ApprovalPersistence;

  constructor(telemetry?: PendingTelemetrySink, persistence?: ApprovalPersistence) {
    this.telemetry = telemetry ?? defaultPendingTelemetrySink;
    this.persistence = persistence;
  }

  /** Registers one owner-bound approval request, deduplicating identical active requests. */
  request(args: PendingRequestArgs): PendingApprovalView {
    const identity = this.identityFor(args);
    const existingId = this.identityIndex.get(identity);
    const existing = existingId ? this.records.get(existingId) : undefined;
    if (existing) return this.toView(existing);

    const requestId = randomUUID();
    const timeoutMs = args.timeoutMs && args.timeoutMs > 0 ? args.timeoutMs : DEFAULT_TIMEOUT_MS;
    const createdAt = new Date();
    const record: PendingApprovalRecord = {
      requestId,
      toolName: args.toolName,
      toolInput: args.toolInput,
      sessionId: args.sessionId,
      authSub: args.authSub,
      inputDigest: approvalInputDigest(args.approvalInput),
      status: "pending",
      createdAt: createdAt.toISOString(),
      deadline: new Date(createdAt.getTime() + timeoutMs).toISOString(),
      timer: setTimeout(() => this.expire(requestId), timeoutMs),
    };
    this.records.set(requestId, record);
    this.identityIndex.set(identity, requestId);
    this.telemetry({
      event: "ask_pending_requested",
      requestId,
      toolName: args.toolName,
      sessionId: args.sessionId,
      authSub: args.authSub,
      inputDigest: record.inputDigest,
      timeoutMs,
      ts: record.createdAt,
    });
    this.persist((p) => p.insertPending(this.toView(record), args.authSub));
    return this.toView(record);
  }

  /** Lists only pending requests owned by the authenticated subject. */
  list(authSub: string): PendingApprovalView[] {
    return Array.from(this.records.values())
      .filter((record) => record.authSub === authSub && record.status === "pending")
      .map((record) => this.toView(record));
  }

  /** Applies an explicit owner-authenticated decision; approved records remain consumable once. */
  respond(requestId: string, decision: PendingDecision, authSub: string): boolean {
    const record = this.records.get(requestId);
    if (!record || record.authSub !== authSub || record.status !== "pending") return false;

    this.telemetry({
      event: "ask_pending_resolved",
      requestId,
      toolName: record.toolName,
      sessionId: record.sessionId,
      authSub,
      decision,
      via: "user",
      ts: new Date().toISOString(),
    });
    this.persist((p) => p.markResolved(requestId, decision, "user"));
    if (decision === "allow") {
      record.status = "approved";
    } else {
      this.remove(record);
    }
    return true;
  }

  /** Atomically consumes one approved decision and returns its stable operation ID. */
  consumeApproved(args: PendingConsumeArgs): string | undefined {
    const identity = this.identityFor(args);
    const consumed = args.reuseAfterConsume ? this.consumedByIdentity.get(identity) : undefined;
    if (consumed) {
      if (Date.now() >= Date.parse(consumed.deadline)) {
        this.removeConsumed(identity);
      } else {
        this.telemetry({
          event: "ask_approval_operation_reused",
          requestId: consumed.operationId,
          toolName: args.toolName,
          sessionId: args.sessionId,
          authSub: args.authSub,
          ts: new Date().toISOString(),
        });
        return consumed.operationId;
      }
    }
    const requestId = this.identityIndex.get(identity);
    const record = requestId ? this.records.get(requestId) : undefined;
    if (!record || record.status !== "approved") return undefined;
    if (Date.now() >= Date.parse(record.deadline)) {
      this.expire(record.requestId);
      return undefined;
    }
    this.remove(record);
    if (args.reuseAfterConsume) {
      this.consumedByIdentity.set(identity, {
        operationId: record.requestId,
        deadline: record.deadline,
        timer: setTimeout(
          () => this.removeConsumed(identity),
          Math.max(Date.parse(record.deadline) - Date.now(), 0),
        ),
      });
    }
    this.telemetry({
      event: "ask_approval_consumed",
      requestId: record.requestId,
      toolName: record.toolName,
      sessionId: record.sessionId,
      authSub: record.authSub,
      inputDigest: record.inputDigest,
      ts: new Date().toISOString(),
    });
    return record.requestId;
  }

  size(): number {
    return this.records.size;
  }

  /** Revokes every active record during tests or shutdown. */
  clearAll(reason: PendingDecision = "deny"): void {
    for (const record of Array.from(this.records.values())) {
      this.remove(record);
      if (record.status === "pending") {
        this.persist((p) => p.markResolved(record.requestId, reason, "user"));
      }
    }
    for (const identity of Array.from(this.consumedByIdentity.keys())) {
      this.removeConsumed(identity);
    }
  }

  private expire(requestId: string): void {
    const record = this.records.get(requestId);
    if (!record) return;
    this.remove(record);
    this.telemetry({
      event: "ask_pending_resolved",
      requestId,
      toolName: record.toolName,
      sessionId: record.sessionId,
      authSub: record.authSub,
      decision: "deny",
      via: "timeout",
      ts: new Date().toISOString(),
    });
    if (record.status === "pending") {
      this.persist((p) => p.markResolved(requestId, "deny", "timeout"));
    }
  }

  private remove(record: PendingApprovalRecord): void {
    clearTimeout(record.timer);
    this.records.delete(record.requestId);
    this.identityIndex.delete(
      this.identityKey(record.authSub, record.sessionId, record.toolName, record.inputDigest),
    );
  }

  private removeConsumed(identity: string): void {
    const record = this.consumedByIdentity.get(identity);
    if (!record) return;
    clearTimeout(record.timer);
    this.consumedByIdentity.delete(identity);
  }

  private identityFor(args: PendingConsumeArgs): string {
    return this.identityKey(
      args.authSub,
      args.sessionId,
      args.toolName,
      approvalInputDigest(args.approvalInput),
    );
  }

  private identityKey(
    authSub: string,
    sessionId: string,
    toolName: string,
    inputDigest: string,
  ): string {
    return `${authSub}\u0000${sessionId}\u0000${toolName}\u0000${inputDigest}`;
  }

  private toView(record: PendingApprovalRecord): PendingApprovalView {
    const { requestId, toolName, toolInput, sessionId, inputDigest, createdAt, deadline } = record;
    return { requestId, toolName, toolInput, sessionId, inputDigest, createdAt, deadline };
  }

  private persist(fn: (persistence: ApprovalPersistence) => Promise<void>): void {
    if (!this.persistence) return;
    try {
      void fn(this.persistence).catch((error) => {
        console.error("[pending] 审批审计落库失败（审批流不受影响）:", error);
      });
    } catch (error) {
      console.error("[pending] 审批审计落库失败（审批流不受影响）:", error);
    }
  }
}

function stableStringify(value: unknown): string {
  if (value === undefined) return "undefined";
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(object[key])}`)
    .join(",")}}`;
}

export const pendingApprovals = new PendingApprovalsStore(undefined, {
  insertPending,
  markResolved,
});
