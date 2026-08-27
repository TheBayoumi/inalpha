import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

/** Proxies one owner-authenticated approval decision to the private Mastra API. */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const requestId = (await params).id;
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  const decision = (body as { decision?: unknown } | null)?.decision;
  if (decision !== "allow" && decision !== "deny") {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  try {
    const result = await backendFetch<unknown>(
      "mastra",
      `/permissions/${encodeURIComponent(requestId)}/respond`,
      { method: "POST", body: { decision }, timeoutMs: 5_000 },
    );
    return NextResponse.json(result);
  } catch (error) {
    const candidate = (error as { status?: unknown } | null)?.status;
    const status = typeof candidate === "number" ? candidate : 502;
    return NextResponse.json({ error: "approval_failed" }, { status });
  }
}
