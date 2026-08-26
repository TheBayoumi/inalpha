/** services/evolver 的 owner-scoped API 客户端。 */
import { HttpClient, HttpClientError } from "./http.js";
import type { EvolutionLLMSnapshot } from "../mastra/llm/evolution-snapshot.js";

export type EvolutionConfig = {
  venue: string;
  symbol: string;
  timeframe: string;
  from_ts: string;
  as_of: string;
  initial_cash?: number;
  fee_rate?: number;
  validation_split?: number;
};

export type CandidateResult = {
  candidate_id: string;
  run_id: string;
  slot: number;
  generation: number;
  stage: string;
  outcome: string;
  source_code: string | null;
  source_hash: string | null;
  unified_diff: string | null;
  mutation_hint: string | null;
  llm_cost_usd: number | null;
  fitness: number | null;
  evaluation_snapshot: Record<string, unknown> | null;
  audit_snapshot: Record<string, unknown> | null;
  contract_snapshot: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  overfitting_risk: string;
  created_at: string | null;
  updated_at: string | null;
};

export type RunStatusResult = {
  run_id: string;
  seed_strategy_id: string;
  budget: number;
  config: Record<string, unknown>;
  status: "queued" | "running" | "cancelling" | "completed" | "failed" | "aborted";
  active_stage: string | null;
  llm_cost_usd: number;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  dataset_manifest: Record<string, unknown> | null;
  seed_report_snapshot: Record<string, unknown> | null;
  baseline_snapshot: Record<string, unknown> | null;
  failure_code: string | null;
  failure_message: string | null;
  attempted: number;
  succeeded: number;
  rejected: number;
  candidates: CandidateResult[];
};

export type RunListResult = { items: RunStatusResult[]; next_cursor: string | null };

export class EvolverClient {
  private readonly http: HttpClient;

  constructor(options: { baseUrl: string; token: string; timeoutMs?: number }) {
    this.http = new HttpClient(options);
  }

  async startRun(options: {
    budget?: number;
    seedStrategyId?: string;
    config: EvolutionConfig;
    idempotencyKey: string;
    approvalToken: string;
    llmSnapshot: EvolutionLLMSnapshot;
  }): Promise<RunStatusResult> {
    const body = {
      budget: options.budget ?? 4,
      seed_strategy_id: options.seedStrategyId ?? "sma_cross_v1",
      config: options.config,
      llm: options.llmSnapshot,
    };
    const headers = {
      "Idempotency-Key": options.idempotencyKey,
      "X-Evolution-Approval": options.approvalToken,
    };
    try {
      return await this.http.post<RunStatusResult>("/api/v1/runs", body, headers);
    } catch (error) {
      if (!(error instanceof HttpClientError) || ![502, 504].includes(error.status)) throw error;
      return await this.http.post<RunStatusResult>("/api/v1/runs", body, headers);
    }
  }

  async listRuns(limit = 20): Promise<RunListResult> {
    return await this.http.get<RunListResult>("/api/v1/runs", { limit });
  }

  async getRun(runId: string): Promise<RunStatusResult> {
    return await this.http.get<RunStatusResult>(`/api/v1/runs/${runId}`);
  }

  async getCandidate(candidateId: string): Promise<CandidateResult> {
    return await this.http.get<CandidateResult>(`/api/v1/candidates/${candidateId}`);
  }

  async abortRun(runId: string): Promise<RunStatusResult> {
    return await this.http.post<RunStatusResult>(`/api/v1/runs/${runId}/abort`, {});
  }
}
