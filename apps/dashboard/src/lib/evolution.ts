import type { EvolutionRunStatus } from "./types";

export const ACTIVE_EVOLUTION_STATUSES = new Set<EvolutionRunStatus>([
  "queued",
  "running",
  "cancelling",
]);

export const EVOLUTION_REFRESH_MS = 4_000;

export function evolutionRefreshInterval(
  status: EvolutionRunStatus | undefined,
): number {
  return status === undefined || isEvolutionActive(status) ? EVOLUTION_REFRESH_MS : 0;
}

export function evolutionTone(status: EvolutionRunStatus) {
  if (status === "completed") return "bull" as const;
  if (status === "running") return "cyan" as const;
  if (status === "queued" || status === "cancelling") return "gold" as const;
  if (status === "failed") return "fox" as const;
  return "muted" as const;
}

export function isEvolutionActive(status: EvolutionRunStatus): boolean {
  return ACTIVE_EVOLUTION_STATUSES.has(status);
}

export const STAT_TONE_CLASS = {
  bull: "text-bull",
  cyan: "text-cyan",
  fox: "text-fox-red",
  muted: "text-fg-muted",
} as const;
