import { beforeEach, describe, expect, it, vi } from "vitest";

import { BackendError, backendFetch } from "@/lib/backend";

import { POST } from "./route";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/backend", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/backend")>();
  return { ...actual, backendFetch: vi.fn() };
});

const mockedBackendFetch = vi.mocked(backendFetch);

function request(body: unknown): Request {
  return new Request("http://dashboard.test/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("registration BFF", () => {
  beforeEach(() => mockedBackendFetch.mockReset());

  it("forwards the application without a service token", async () => {
    mockedBackendFetch.mockResolvedValue({ accepted: true });
    const body = {
      email: "applicant@example.com",
      display_name: "Applicant",
      application_note: "Factor validation",
    };

    const response = await POST(request(body));

    expect(response.status).toBe(202);
    expect(mockedBackendFetch).toHaveBeenCalledWith("paper", "/auth/register", {
      auth: false,
      method: "POST",
      body,
      timeoutMs: 15_000,
    });
  });

  it("maps validation and throttle failures without exposing backend details", async () => {
    mockedBackendFetch.mockRejectedValueOnce(new BackendError(422, "invalid", { secret: true }));
    mockedBackendFetch.mockRejectedValueOnce(new BackendError(429, "limited"));

    const invalid = await POST(request({}));
    const limited = await POST(request({}));

    expect(invalid.status).toBe(400);
    expect(await invalid.json()).toEqual({ error: "INVALID_APPLICATION" });
    expect(limited.status).toBe(429);
    expect(await limited.json()).toEqual({ error: "RATE_LIMITED" });
  });

  it("rejects non-JSON and oversized public requests before forwarding", async () => {
    const wrongType = new Request("http://dashboard.test/api/auth/register", {
      method: "POST",
      body: "plain text",
    });
    const oversized = new Request("http://dashboard.test/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ application_note: "x".repeat(17 * 1024) }),
    });

    const wrongTypeResponse = await POST(wrongType);
    const oversizedResponse = await POST(oversized);

    expect(wrongTypeResponse.status).toBe(415);
    expect(oversizedResponse.status).toBe(413);
    expect(mockedBackendFetch).not.toHaveBeenCalled();
  });
});
