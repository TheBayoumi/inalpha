"use client";

import { useTranslations } from "next-intl";

import { STAT_TONE_CLASS } from "@/lib/evolution";
import { cn } from "@/lib/cn";

/** 演化列表顶部聚合指标。 */
export function EvolutionStats({
  total,
  active,
  cost,
  rejected,
}: {
  total: number;
  active: number;
  cost: number;
  rejected: number;
}) {
  const t = useTranslations("evolution");
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Stat label={t("runs")} value={String(total)} tone="bull" />
      <Stat label={t("running")} value={String(active)} tone={active > 0 ? "cyan" : "muted"} />
      <Stat label={t("llmCost")} value={`$${cost.toFixed(4)}`} tone="muted" />
      <Stat label={t("rejected")} value={String(rejected)} tone="fox" />
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: keyof typeof STAT_TONE_CLASS }) {
  return <div className="rounded-xl border border-border-subtle bg-bg-elev/30 px-4 py-3 backdrop-blur-sm"><div className="font-mono text-[10px] uppercase tracking-[0.16em] text-fg-muted">{label}</div><div className={cn("mt-1.5 font-mono text-xl leading-none", STAT_TONE_CLASS[tone])}>{value}</div></div>;
}
