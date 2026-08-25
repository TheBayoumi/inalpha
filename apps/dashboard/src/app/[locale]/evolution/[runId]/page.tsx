import { setRequestLocale } from "next-intl/server";

import { EvolutionRunDetailClient } from "@/components/evolution/EvolutionRunDetailClient";

/** 单次 E1 演化运行及其 slot 结果。 */
export default async function EvolutionRunPage({
  params,
}: {
  params: Promise<{ locale: string; runId: string }>;
}) {
  const { locale, runId } = await params;
  setRequestLocale(locale);
  return <EvolutionRunDetailClient runId={runId} />;
}
