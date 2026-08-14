"use client";

import { useTranslations } from "next-intl";

import type { EvolutionRun } from "@/lib/types";
import { Panel } from "@/components/ui/Panel";

/** 展示 seed、基准、冻结数据 manifest 与失败信息。 */
export function EvolutionRunData({ run }: { run: EvolutionRun }) {
  const t = useTranslations("evolution.detail");
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <Panel title={t("summary")}>
        <dl className="grid grid-cols-2 gap-4 p-4 text-sm">
          <Item label={t("stage")} value={run.active_stage ?? "—"} />
          <Item label={t("attempts")} value={`${run.attempted}/${run.budget}`} />
          <Item label={t("succeeded")} value={String(run.succeeded)} />
          <Item label={t("rejected")} value={String(run.rejected)} />
          <Item label={t("cost")} value={`$${run.llm_cost_usd.toFixed(4)}`} />
          <Item label={t("failure")} value={run.failure_code ?? "—"} />
        </dl>
        {run.failure_message && (
          <p className="border-t border-border-subtle px-4 py-3 text-sm text-fox-red">
            {run.failure_message}
          </p>
        )}
      </Panel>
      <Panel title={t("dataset")}>
        <ObjectRows
          value={run.dataset_manifest}
          empty={t("notAvailable")}
          preferred={["venue", "symbol", "requested_timeframe", "latest_bar_ts", "bar_count", "freshness_lag_seconds", "content_sha256"]}
        />
      </Panel>
      <Panel title={t("seedReport")}>
        <ObjectRows value={run.seed_report_snapshot} empty={t("notAvailable")} />
      </Panel>
      <Panel title={t("baseline")}>
        <ObjectRows value={run.baseline_snapshot} empty={t("notAvailable")} />
      </Panel>
    </div>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0"><dt className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">{label}</dt><dd className="mt-1 break-all font-mono text-xs text-fg">{value}</dd></div>;
}

function ObjectRows({ value, empty, preferred }: { value: Record<string, unknown> | null; empty: string; preferred?: string[] }) {
  if (!value) return <p className="p-4 text-sm text-fg-muted">{empty}</p>;
  const entries = preferred
    ? preferred.filter((key) => key in value).map((key) => [key, value[key]] as const)
    : Object.entries(value).filter(([, item]) => typeof item !== "object").slice(0, 12);
  return <dl className="divide-y divide-border-subtle/60 px-4">{entries.map(([key, item]) => <div key={key} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] gap-3 py-2 text-xs"><dt className="font-mono text-fg-muted">{key}</dt><dd className="break-all text-right font-mono text-fg">{formatValue(item)}</dd></div>)}</dl>;
}

function formatValue(value: unknown): string {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  if (typeof value === "boolean") return value ? "true" : "false";
  return value == null ? "—" : String(value);
}
