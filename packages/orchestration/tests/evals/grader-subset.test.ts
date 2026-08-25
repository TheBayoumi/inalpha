import { describe, expect, it } from "vitest";

import { deepSubset } from "../../src/evals/grader.js";

describe("agent eval deep subset", () => {
  it("matches nested partial objects", () => {
    expect(
      deepSubset(
        { query: { symbol: "AAPL", venue: "nasdaq" }, limit: 10 },
        { query: { symbol: "AAPL" } },
      ),
    ).toBe(true);
  });

  it("matches array prefixes recursively", () => {
    expect(
      deepSubset(
        { rows: [{ value: 1, extra: true }] },
        { rows: [{ value: 1 }] },
      ),
    ).toBe(true);
  });

  it("rejects mismatched, missing, short, and primitive values", () => {
    const cases: Array<[unknown, unknown]> = [
      [{ nested: { value: 1 } }, { nested: { value: 2 } }],
      [{}, { missing: true }],
      [[1], [1, 2]],
      [null, { value: 1 }],
      ["1", 1],
    ];
    for (const [actual, expected] of cases) {
      expect(deepSubset(actual, expected)).toBe(false);
    }
  });
});
