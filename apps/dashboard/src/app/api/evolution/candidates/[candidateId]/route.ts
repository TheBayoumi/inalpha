import { NextResponse } from "next/server";

import { backendFetch, BackendError } from "@/lib/backend";
import { isEvolutionEnabled } from "@/lib/evolution-capability";
import type { EvolutionCandidateDetailPayload, EvolutionCandidateSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ candidateId: string }> },
) {
  if (!isEvolutionEnabled()) {
    return NextResponse.json(
      { error: "evolution service is not enabled", code: "EVOLUTION_SERVICE_DISABLED" },
      { status: 503 },
    );
  }
  const { candidateId } = await params;
  const valid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(candidateId);
  if (!valid) return NextResponse.json({ error: "invalid candidate id" }, { status: 400 });
  try {
    const candidate = await backendFetch<EvolutionCandidateSummary>(
      "evolver",
      `/api/v1/candidates/${candidateId}`,
      { timeoutMs: 5000 },
    );
    const payload: EvolutionCandidateDetailPayload = {
      candidate,
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
