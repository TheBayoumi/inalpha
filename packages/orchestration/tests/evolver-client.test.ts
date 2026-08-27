import { generateKeyPairSync } from "node:crypto";

import { jwtVerify } from "jose";
import { afterEach, describe, expect, it, vi } from "vitest";

import { verifyToken } from "../src/auth.js";
import { EvolverClient } from "../src/clients/evolver.js";
import { AUTH_SUB_KEY } from "../src/hooks/with-hooks.js";
import {
  APPROVAL_OPERATION_ID_KEY,
  buildEvolutionLLMSnapshot,
  USER_LLM_SNAPSHOT_KEY,
} from "../src/mastra/llm/evolution-snapshot.js";
import { getApprovedEvolutionRunContext } from "../src/tools/evolver-shared.js";

const snapshot = buildEvolutionLLMSnapshot({
  id: "config-1",
  provider: "deepseek",
  model: "deepseek-v4-pro",
  api_key: "not-forwarded",
});

function response(status: number): Response {
  return new Response(
    JSON.stringify(
      status === 200
        ? { run_id: "run-1", status: "queued" }
        : { code: `HTTP_${status}`, message: "temporary upstream failure" },
    ),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function options() {
  return {
    budget: 1,
    seedStrategyId: "sma_cross_v1",
    config: {
      venue: "binance",
      symbol: "BTCUSDT",
      timeframe: "1h",
      from_ts: "2026-08-01T00:00:00Z",
      as_of: "2026-08-02T00:00:00Z",
      initial_cash: 10_000,
    },
    idempotencyKey: "approval-operation-1",
    approvalToken: "approval-token",
    credentialGrant: "credential-grant",
    llmSnapshot: snapshot,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("EvolverClient", () => {
  it("mints a short-lived approval JWT bound to owner, operation, and snapshot", async () => {
    const keys = generateKeyPairSync("ed25519");
    vi.stubEnv(
      "EVOLUTION_CREDENTIAL_PRIVATE_KEY_B64",
      keys.privateKey.export({ format: "der", type: "pkcs8" }).toString("base64"),
    );
    const requestContext = new Map<string, unknown>([
      [AUTH_SUB_KEY, "user:alice"],
      [APPROVAL_OPERATION_ID_KEY, "approval-operation-1"],
      [USER_LLM_SNAPSHOT_KEY, snapshot],
    ]);

    const approved = await getApprovedEvolutionRunContext(requestContext);
    const payload = await verifyToken(approved.approvalToken);
    const { payload: credential } = await jwtVerify(
      approved.credentialGrant,
      keys.publicKey,
      { algorithms: ["EdDSA"], audience: "inalpha-dashboard-credential" },
    );

    expect(payload).toMatchObject({
      sub: "user:alice",
      token_use: "evolution_approval",
      operation_id: "approval-operation-1",
      llm_config_digest: snapshot.config_digest,
    });
    expect(Number(payload.exp) - Number(payload.iat)).toBe(300);
    expect(credential).toMatchObject({
      sub: "user:alice",
      token_use: "evolution_credential",
      config_id: "config-1",
      operation_id: "approval-operation-1",
      llm_config_digest: snapshot.config_digest,
    });
    expect(Number(credential.exp) - Number(credential.iat)).toBe(108_000);
  });

  it("retries 502/504 with the same approval-derived operation ID", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(504))
      .mockResolvedValueOnce(response(200));
    vi.stubGlobal("fetch", fetchMock);

    const result = await new EvolverClient({
      baseUrl: "http://evolver.test",
      token: "owner-token",
    }).startRun(options());

    expect(result.status).toBe("queued");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    for (const call of fetchMock.mock.calls) {
      const init = call[1] as RequestInit;
      expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe(
        "approval-operation-1",
      );
      expect((init.headers as Record<string, string>)["X-Evolution-Approval"]).toBe(
        "approval-token",
      );
      expect((init.headers as Record<string, string>)["X-Evolution-Credential"]).toBe(
        "credential-grant",
      );
      expect(init.body).not.toContain("not-forwarded");
    }
  });

  it("retries a 502 once but does not retry other client errors", async () => {
    const retryable = vi
      .fn()
      .mockResolvedValueOnce(response(502))
      .mockResolvedValueOnce(response(200));
    vi.stubGlobal("fetch", retryable);
    await expect(
      new EvolverClient({ baseUrl: "http://evolver.test", token: "owner-token" }).startRun(
        options(),
      ),
    ).resolves.toMatchObject({ status: "queued" });
    expect(retryable).toHaveBeenCalledTimes(2);

    const nonRetryable = vi.fn().mockResolvedValue(response(403));
    vi.stubGlobal("fetch", nonRetryable);
    await expect(
      new EvolverClient({ baseUrl: "http://evolver.test", token: "owner-token" }).startRun(
        options(),
      ),
    ).rejects.toThrow();
    expect(nonRetryable).toHaveBeenCalledTimes(1);
  });
});
