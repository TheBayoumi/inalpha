import { beforeEach, describe, expect, it, vi } from "vitest";

import { backendFetch } from "@/lib/backend";

import { GET } from "./route";

vi.mock("@/lib/backend", () => ({ backendFetch: vi.fn() }));

const mockedBackendFetch = vi.mocked(backendFetch);

describe("admin waitlist BFF", () => {
  beforeEach(() => mockedBackendFetch.mockReset());

  it("returns only the backend-approved waitlist payload", async () => {
    const payload = { users: [{ subject: "user:one", email: "one@example.com" }] };
    mockedBackendFetch.mockResolvedValue(payload);

    const response = await GET();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(payload);
    expect(mockedBackendFetch).toHaveBeenCalledWith("paper", "/auth/waitlist");
  });
});
