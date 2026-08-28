import { beforeEach, describe, expect, it, vi } from "vitest";

import { BackendError, backendFetch } from "@/lib/backend";
import { createSessionToken } from "@/lib/session";

import { POST } from "./route";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/backend", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/backend")>();
  return { ...actual, backendFetch: vi.fn() };
});
vi.mock("@/lib/session", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/session")>();
  return { ...actual, createSessionToken: vi.fn() };
});

const mockedBackendFetch = vi.mocked(backendFetch);
const mockedCreateSessionToken = vi.mocked(createSessionToken);

function loginRequest(): Request {
  return new Request("http://dashboard.test/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "applicant@example.com", password: "password" }),
  });
}

describe("login BFF access status", () => {
  beforeEach(() => {
    mockedBackendFetch.mockReset();
    mockedCreateSessionToken.mockReset();
  });

  it("preserves the generic inactive status after valid credentials", async () => {
    const code = "ACCOUNT_INACTIVE";
    mockedBackendFetch.mockRejectedValue(new BackendError(403, code, { code }));

    const response = await POST(loginRequest());

    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: code });
    expect(mockedCreateSessionToken).not.toHaveBeenCalled();
  });

  it("does not expose an unknown forbidden response as an account status", async () => {
    mockedBackendFetch.mockRejectedValue(new BackendError(403, "forbidden"));

    const response = await POST(loginRequest());

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ error: "登录服务暂不可用,请稍后重试" });
    expect(mockedCreateSessionToken).not.toHaveBeenCalled();
  });

  it("rejects an oversized public request before calling the backend", async () => {
    const request = new Request("http://dashboard.test/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "a@example.com", password: "x".repeat(17_000) }),
    });

    const response = await POST(request);

    expect(response.status).toBe(413);
    expect(mockedBackendFetch).not.toHaveBeenCalled();
  });
});
