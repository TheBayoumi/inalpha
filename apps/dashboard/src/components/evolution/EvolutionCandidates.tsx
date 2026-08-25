"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import type { EvolutionCandidateSummary } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";

/** 按 slot 展示一代候选及其阶段结果。 */
export function EvolutionCandidates({
  candidates,
}: {
  candidates: EvolutionCandidateSummary[];
}) {
  const t = useTranslations("evolution.detail");
  if (candidates.length === 0) {
    return <p className="p-8 text-center text-sm text-fg-muted">{t("noCandidates")}</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b border-border-subtle font-mono text-[10px] uppercase tracking-wider text-fg-muted">
          <tr><th className="px-4 py-2 text-left">{t("slot")}</th><th className="px-4 py-2 text-left">{t("outcome")}</th><th className="px-4 py-2 text-left">{t("stage")}</th><th className="px-4 py-2 text-right">{t("fitness")}</th><th className="px-4 py-2 text-right">{t("cost")}</th></tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => (
            <tr key={candidate.candidate_id} className="border-b border-border-subtle/60 last:border-0">
              <td className="px-4 py-3 font-mono"><Link href={`/evolution/candidates/${candidate.candidate_id}`} className="text-cyan hover:underline">#{candidate.slot + 1}</Link></td>
              <td className="px-4 py-3"><StatusBadge label={candidate.outcome} tone={outcomeTone(candidate.outcome)} /></td>
              <td className="px-4 py-3 font-mono text-xs text-fg-muted">{candidate.stage}</td>
              <td className="px-4 py-3 text-right font-mono">{candidate.fitness?.toFixed(4) ?? "—"}</td>
              <td className="px-4 py-3 text-right font-mono text-fg-muted">${(candidate.llm_cost_usd ?? 0).toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function outcomeTone(outcome: string): "bull" | "fox" | "gold" | "muted" {
  if (outcome === "succeeded") return "bull";
  if (outcome === "pending") return "gold";
  if (outcome === "cancelled") return "muted";
  return "fox";
}
