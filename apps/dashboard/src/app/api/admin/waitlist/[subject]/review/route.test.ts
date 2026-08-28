import { beforeEach, describe, expect, it, vi } from "vitest";

import { backendFetch } from "@/lib/backend";

import { reviewErrorResponse } from "./review-error";
import { POST } from "./route";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/backend", () => ({ backendFetch: vi.fn() }));

const mockedBackendFetch = vi.mocked(backendFetch);

function request(body: unknown): Request {
  return new Request("http://dashboard.test/api/admin/waitlist/user/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function context(subject = "user:applicant/one") {
  return { params: Promise.resolve({ subject }) };
}

describe("admin waitlist review BFF", () => {
  beforeEach(() => mockedBackendFetch.mockReset());

  it("encodes the subject and forwards a valid decision", async () => {
    mockedBackendFetch.mockResolvedValue({
      subject: "user:applicant/one",
      access_status: "invited",
      activation_token: "one-time-token",
    });

    const response = await POST(
      request({ decision: "approve", expected_reviewed_at: null }),
      context(),
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      subject: "user:applicant/one",
      access_status: "invited",
      activation_token: "one-time-token",
    });
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(mockedBackendFetch).toHaveBeenCalledWith(
      "paper",
      "/auth/waitlist/user%3Aapplicant%2Fone/review",
      {
        method: "POST",
        body: { decision: "approve", expected_reviewed_at: null },
      },
    );
  });

  it("rejects malformed decisions before calling the backend", async () => {
    const response = await POST(request({ decision: "activate" }), context());

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "INVALID_DECISION" });
    expect(mockedBackendFetch).not.toHaveBeenCalled();
  });

  async function expectMappedFailure(
    backendStatus: number,
    status: number,
    code: string,
  ) {
    const response = reviewErrorResponse({ status: backendStatus });

    expect(response.status).toBe(status);
    expect(await response.json()).toEqual({ error: code });
  }

  it("maps forbidden review failures", async () => {
    await expectMappedFailure(403, 403, "FORBIDDEN");
  });

  it("maps repeat review conflicts", async () => {
    await expectMappedFailure(409, 409, "ALREADY_REVIEWED");
  });

  it("maps unexpected review failures", async () => {
    await expectMappedFailure(500, 502, "SERVICE_UNAVAILABLE");
  });
});
