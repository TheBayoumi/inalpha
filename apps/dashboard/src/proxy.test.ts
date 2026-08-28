import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next-intl/middleware", () => ({
  default: () => vi.fn(() => new Response(null, { status: 200 })),
}));

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

/** Load middleware after setting production auth flags because they are module constants. */
async function productionMiddleware() {
  vi.stubEnv("NODE_ENV", "production");
  vi.stubEnv("AUTH_ENABLED", "true");
  return (await import("./proxy")).default;
}

describe("dashboard production proxy", () => {
  it("lets the exact internal credential exchange reach its Ed25519 route verifier", async () => {
    const middleware = await productionMiddleware();
    const response = await middleware(
      new NextRequest("http://dashboard.test/api/internal/llm-config/config-1", {
        headers: { Authorization: "Bearer signed-grant" },
      }),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it("keeps other cookie-less API paths behind the session gate", async () => {
    const middleware = await productionMiddleware();
    const response = await middleware(
      new NextRequest("http://dashboard.test/api/evolution", {
        headers: { Authorization: "Bearer signed-grant" },
      }),
    );

    expect(response.status).toBe(401);
  });

  it.each(["/register", "/activate", "/api/auth/register", "/api/auth/activate"])(
    "keeps the public access flow reachable at %s",
    async (pathname) => {
      const middleware = await productionMiddleware();
      const response = await middleware(
        new NextRequest(`http://dashboard.test${pathname}`),
      );

      expect(response.status).toBe(200);
      expect(response.headers.get("x-middleware-next")).toBe("1");
    },
  );
});
