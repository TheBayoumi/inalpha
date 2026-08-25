import { describe, expect, it } from "vitest";

import {
  EVOLUTION_REFRESH_MS,
  evolutionRefreshInterval,
  evolutionTone,
  isEvolutionActive,
} from "./evolution";

const ACTIVE = ["queued", "running", "cancelling"] as const;
const TERMINAL = ["completed", "failed", "aborted"] as const;

describe("evolution status helpers", () => {
  it("仅 active 状态继续轮询", () => {
    for (const status of ACTIVE) {
      expect(isEvolutionActive(status)).toBe(true);
      expect(evolutionRefreshInterval(status)).toBe(EVOLUTION_REFRESH_MS);
    }
    for (const status of TERMINAL) {
      expect(isEvolutionActive(status)).toBe(false);
      expect(evolutionRefreshInterval(status)).toBe(0);
    }
  });

  it("首帧未知时允许获取后续状态", () => {
    expect(evolutionRefreshInterval(undefined)).toBe(EVOLUTION_REFRESH_MS);
  });

  it("状态颜色使用静态语义映射", () => {
    expect(evolutionTone("completed")).toBe("bull");
    expect(evolutionTone("running")).toBe("cyan");
    expect(evolutionTone("queued")).toBe("gold");
    expect(evolutionTone("failed")).toBe("fox");
    expect(evolutionTone("aborted")).toBe("muted");
  });
});
