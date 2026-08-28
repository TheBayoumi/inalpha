import { beforeEach, describe, expect, it, vi } from "vitest";

import { backendFetch } from "@/lib/backend";

import { activateErrorResponse } from "./activate-error";
import { POST } from "./route";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/backend", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/backend")>();
  return { ...actual, backendFetch: vi.fn() };
});

const mockedBackendFetch = vi.mocked(backendFetch);

function request(body: unknown): Request {
  return new Request("http://dashboard.test/api/auth/activate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("activation BFF", () => {
  beforeEach(() => mockedBackendFetch.mockReset());

  it("forwards the one-time token without service authentication", async () => {
    mockedBackendFetch.mockResolvedValue({ activated: true });
    const body = { token: "t".repeat(43), password: "long-enough-password" };

    const response = await POST(request(body));

    expect(response.status).toBe(200);
    expect(mockedBackendFetch).toHaveBeenCalledWith("paper", "/auth/activate", {
      auth: false,
      method: "POST",
      body,
      timeoutMs: 15_000,
    });
  });

  it.each([
    [400, 400, "INVALID_ACTIVATION"],
    [409, 409, "ACTIVATION_USED"],
    [429, 429, "ACTIVATION_BUSY"],
    [500, 502, "SERVICE_UNAVAILABLE"],
  ] as const)("maps backend status %s", async (backendStatus, status, code) => {
    const response = activateErrorResponse({ status: backendStatus });

    expect(response.status).toBe(status);
    expect(await response.json()).toEqual({ error: code });
  });

  it("adds Retry-After when activation capacity is saturated", async () => {
    const response = activateErrorResponse({ status: 429 });

    expect(response.headers.get("Retry-After")).toBe("5");
  });
});
