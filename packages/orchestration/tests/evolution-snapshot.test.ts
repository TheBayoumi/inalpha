import { describe, expect, it } from "vitest";

import {
  buildEvolutionLLMSnapshot,
  computeEvolutionLLMConfigDigest,
} from "../src/mastra/llm/evolution-snapshot.js";

describe("evolution LLM snapshot", () => {
  it("matches the Python cross-language digest contract without copying the API key", () => {
    const snapshot = buildEvolutionLLMSnapshot({
      id: "config-1",
      provider: "deepseek",
      model: "deepseek-v4-pro",
      api_key: "must-not-be-copied",
      custom_base_url: "https://api.deepseek.com/",
    });

    expect(snapshot.config_digest).toBe(
      "a4635b0c80f69b6054bdc2330b78cb98d9c81c849d476e7d01f1b8d626015c2c",
    );
    expect(JSON.stringify(snapshot)).not.toContain("must-not-be-copied");
    expect(computeEvolutionLLMConfigDigest(snapshot)).toBe(snapshot.config_digest);
  });

  it("fails closed for providers the Python runtime cannot execute", () => {
    expect(() =>
      buildEvolutionLLMSnapshot({
        id: "config-2",
        provider: "anthropic",
        api_key: "test-key",
      }),
    ).toThrow("pricing is unavailable");
  });

  it("rejects credentials, query strings, and non-HTTP base URLs", () => {
    for (const custom_base_url of [
      "https://user:pass@example.com/v1",
      "https://example.com/v1?token=x",
      "ftp://example.com/v1",
    ]) {
      expect(() =>
        buildEvolutionLLMSnapshot({
          id: "config-3",
          provider: "openai",
          api_key: "test-key",
          custom_base_url,
        }),
      ).toThrow();
    }
  });
});
