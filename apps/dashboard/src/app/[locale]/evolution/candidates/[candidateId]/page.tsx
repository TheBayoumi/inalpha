import { setRequestLocale } from "next-intl/server";

import { EvolutionCandidateDetailClient } from "@/components/evolution/EvolutionCandidateDetailClient";

/** 单个 E1 演化 slot 详情。 */
export default async function EvolutionCandidatePage({
  params,
}: {
  params: Promise<{ locale: string; candidateId: string }>;
}) {
  const { locale, candidateId } = await params;
  setRequestLocale(locale);
  return <EvolutionCandidateDetailClient candidateId={candidateId} />;
}
