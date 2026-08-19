import {
  mkdtempSync,
  readFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

import { afterEach, describe, expect, it } from "vitest";

const packageRoot = fileURLToPath(new URL("../../", import.meta.url));
const script = join(packageRoot, "scripts/run-agent-evals.ts");
const temporary: string[] = [];

function run(args: string[]) {
  return spawnSync(process.execPath, ["--import", "tsx", script, ...args], {
    cwd: packageRoot,
    encoding: "utf8",
    timeout: 20_000,
    env: { ...process.env, INALPHA_AGENT_EVAL_LIVE: "" },
  });
}

afterEach(() => {
  for (const path of temporary.splice(0)) rmSync(path, { recursive: true });
});

describe("agent eval CLI integration", () => {
  it("runs one PR case and writes a parseable report", () => {
    const directory = mkdtempSync(join(tmpdir(), "inalpha-eval-cli-"));
    temporary.push(directory);
    const report = join(directory, "report.json");
    const result = run([
      "--suite",
      "pr",
      "--case",
      "permission-direct-order-denied",
      "--report",
      report,
    ]);

    expect(result.status, result.stderr).toBe(0);
    expect(JSON.parse(readFileSync(report, "utf8"))).toMatchObject({
      suite: "pr",
      passed: true,
      total: 1,
    });
  });

  it("writes a structured failure artifact for unknown cases", () => {
    const directory = mkdtempSync(join(tmpdir(), "inalpha-eval-cli-"));
    temporary.push(directory);
    const report = join(directory, "report.json");
    const result = run([
      "--suite",
      "pr",
      "--case",
      "missing-case",
      "--report",
      report,
    ]);

    expect(result.status).toBe(1);
    expect(result.stderr).toContain("eval case not found");
    expect(JSON.parse(readFileSync(report, "utf8"))).toMatchObject({
      passed: false,
      errors: [{ failureClass: "fixture_invalid" }],
    });
  });

  it("refuses live runs without the explicit opt-in", () => {
    const result = run([
      "--suite",
      "live",
      "--case",
      "live-direct-order-refusal",
      "--trials",
      "3",
    ]);

    expect(result.status).toBe(1);
    expect(result.stderr).toContain("INALPHA_AGENT_EVAL_LIVE=1");
  });
});
