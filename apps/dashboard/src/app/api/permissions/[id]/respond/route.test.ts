import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { backendFetch } from "@/lib/backend";

import { POST } from "./route";

vi.mock("@/lib/backend", () => ({ backendFetch: vi.fn() }));

const mockedBackendFetch = vi.mocked(backendFetch);

/** Calls the dynamic approval route with an isolated JSON request. */
async function callRoute(body: string) {
  return await POST(
    new NextRequest("http://dashboard.test/api/permissions/request-1/respond", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    }),
    { params: Promise.resolve({ id: "request-1" }) },
  );
}

beforeEach(() => mockedBackendFetch.mockReset());

describe("approval response BFF", () => {
  it("forwards an explicit owner decision to the private Mastra API", async () => {
    mockedBackendFetch.mockResolvedValue({ ok: true, decision: "allow" });

    const response = await callRoute(JSON.stringify({ decision: "allow" }));

    expect(response.status).toBe(200);
    expect(mockedBackendFetch).toHaveBeenCalledWith(
      "mastra",
      "/permissions/request-1/respond",
      expect.objectContaining({ method: "POST", body: { decision: "allow" } }),
    );
  });

  it("rejects malformed decisions before contacting Mastra", async () => {
    expect((await callRoute("not-json")).status).toBe(400);
    expect((await callRoute(JSON.stringify({ decision: "yes" }))).status).toBe(400);
    expect(mockedBackendFetch).not.toHaveBeenCalled();
  });
});
