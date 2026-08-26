import { SignJWT } from "jose";
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { decryptUserApiKey } from "@/lib/user-preferences";

import { GET } from "./route";

vi.mock("@/lib/user-preferences", () => ({
  decryptUserApiKey: vi.fn(),
}));

const TEST_SECRET = "dashboard-route-test-secret-at-least-32-bytes";
const mockedDecryptUserApiKey = vi.mocked(decryptUserApiKey);

/** Mints an isolated service credential token for this route test. */
async function token(
  overrides: Record<string, unknown> = {},
): Promise<string> {
  const now = Math.floor(Date.now() / 1_000);
  return await new SignJWT({
    token_use: "evolver_credential",
    config_id: "config-1",
    ...overrides,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject("user:alice")
    .setIssuedAt(now)
    .setExpirationTime(now + 300)
    .sign(new TextEncoder().encode(TEST_SECRET));
}

/** Calls the dynamic route with a resolved Next.js params promise. */
async function callRoute(authorization?: string, id = "config-1") {
  const headers = authorization ? { Authorization: authorization } : undefined;
  return await GET(
    new NextRequest(`http://dashboard.test/api/internal/llm-config/${id}`, { headers }),
    { params: Promise.resolve({ id }) },
  );
}

beforeEach(() => {
  vi.stubEnv("JWT_SECRET", TEST_SECRET);
  mockedDecryptUserApiKey.mockReset();
});

describe("internal owner LLM credential route", () => {
  it("rejects missing authentication and mismatched credential scope", async () => {
    expect((await callRoute()).status).toBe(401);
    expect((await callRoute(`Bearer ${await token({ config_id: "config-2" })}`)).status).toBe(
      403,
    );
    expect(mockedDecryptUserApiKey).not.toHaveBeenCalled();
  });

  it("returns only the requested owner's decrypted config without caching", async () => {
    mockedDecryptUserApiKey.mockResolvedValue({
      id: "config-1",
      provider: "deepseek",
      model: "deepseek-v4-pro",
      custom_base_url: "https://api.deepseek.com",
      api_key: "owner-key",
      api_key_encrypted: "encrypted",
      api_key_nonce: "nonce",
      api_key_tag: "tag",
      created_at: "2026-08-26T00:00:00Z",
      updated_at: "2026-08-26T00:00:00Z",
    });

    const response = await callRoute(`Bearer ${await token()}`);

    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(await response.json()).toEqual({
      config_id: "config-1",
      provider: "deepseek",
      model: "deepseek-v4-pro",
      base_url: "https://api.deepseek.com",
      api_key: "owner-key",
    });
    expect(mockedDecryptUserApiKey).toHaveBeenCalledWith("user:alice", "config-1");
  });

  it("does not fall back to another config when the reference no longer exists", async () => {
    mockedDecryptUserApiKey.mockResolvedValue(null);

    expect((await callRoute(`Bearer ${await token()}`)).status).toBe(404);
  });
});
