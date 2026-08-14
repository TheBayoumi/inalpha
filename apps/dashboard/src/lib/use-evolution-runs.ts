"use client";

import useSWRInfinite from "swr/infinite";

import type { EvolutionPayload } from "./types";
import { jsonFetcher } from "./fetcher";

const PAGE_SIZE = 20;

/** 分页读取演化运行，并保留 keyset cursor。 */
export function useEvolutionRuns() {
  const swr = useSWRInfinite<EvolutionPayload>(
    (index, previous) => {
      if (index > 0 && !previous?.nextCursor) return null;
      const cursor = previous?.nextCursor;
      const query = new URLSearchParams({ limit: String(PAGE_SIZE) });
      if (cursor) query.set("cursor", cursor);
      return `/api/evolution?${query}`;
    },
    jsonFetcher,
    { refreshInterval: 30_000, keepPreviousData: true },
  );
  const pages = swr.data ?? [];
  return {
    ...swr,
    runs: pages.flatMap((page) => page.runs),
    asOf: pages[0]?.asOf,
    hasMore: Boolean(pages.at(-1)?.nextCursor),
    isLoadingMore:
      swr.isValidating && pages.length > 0 && swr.size > pages.length,
    loadMore: () => swr.setSize((size) => size + 1),
  };
}
