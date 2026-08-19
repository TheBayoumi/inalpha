import { describe, expect, it } from "vitest";

import {
  parseEvalArgs,
  parseTrialCount,
} from "../../src/evals/cli.js";

describe("agent eval CLI guards", () => {
  it("parses pnpm forwarding and explicit report arguments", () => {
    expect(
      parseEvalArgs([
        "--",
        "--suite",
        "nightly",
        "--report",
        "/tmp/report.json",
      ]),
    ).toEqual({ suite: "nightly", report: "/tmp/report.json" });
  });

  it("rejects malformed argument pairs", () => {
    expect(() => parseEvalArgs(["--suite"])).toThrow("invalid eval argument");
    expect(() => parseEvalArgs(["--unknown", "value"])).toThrow(
      "invalid eval argument",
    );
  });

  it("limits offline to one trial and live to three through five", () => {
    expect(parseTrialCount(undefined, "pr")).toBe(1);
    expect(parseTrialCount(undefined, "live")).toBe(3);
    expect(parseTrialCount("5", "live")).toBe(5);
    expect(() => parseTrialCount("2", "live")).toThrow("3..5 live");
    expect(() => parseTrialCount("2", "nightly")).toThrow("1 offline");
  });
});
