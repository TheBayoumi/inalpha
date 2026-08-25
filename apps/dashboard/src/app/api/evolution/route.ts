import { NextResponse } from "next/server";

import { backendFetch, BackendError } from "@/lib/backend";
import { isEvolutionEnabled } from "@/lib/evolution-capability";
import type { EvolutionPayload, EvolutionRunSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

type RunsResponse = { items: EvolutionRunSummary[]; next_cursor: string | null };

export async function GET(request: Request) {
  if (!isEvolutionEnabled()) {
    return NextResponse.json(
      { error: "evolution service is not enabled", code: "EVOLUTION_SERVICE_DISABLED" },
      { status: 503 },
    );
  }
  const { searchParams } = new URL(request.url);
  const limit = Math.min(Number(searchParams.get("limit") ?? 50), 50);
  try {
    const raw = await backendFetch<RunsResponse>("evolver", "/api/v1/runs", {
      query: { limit, cursor: searchParams.get("cursor") ?? undefined },
      timeoutMs: 5000,
    });
    const payload: EvolutionPayload = {
      runs: raw.items,
      nextCursor: raw.next_cursor,
      asOf: new Date().toISOString(),
    };
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const status = error instanceof BackendError ? error.status : 500;
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "unknown error" },
      { status },
    );
  }
}
