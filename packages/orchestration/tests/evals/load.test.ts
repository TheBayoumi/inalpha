import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it } from "vitest";

import { loadGoldenTasks } from "../../src/evals/load.js";

const source = fileURLToPath(
  new URL("../../evals/golden/permission-direct-order-denied.json", import.meta.url),
);
const temporary: string[] = [];

afterEach(async () => {
  await Promise.all(temporary.splice(0).map((path) => rm(path, { recursive: true })));
});

describe("loadGoldenTasks", () => {
  it("rejects duplicate ids across files", async () => {
    const directory = await mkdtemp(join(tmpdir(), "inalpha-eval-"));
    temporary.push(directory);
    const content = await readFile(source, "utf8");
    await writeFile(join(directory, "one.json"), content);
    await writeFile(join(directory, "two.json"), content);

    await expect(loadGoldenTasks(directory, "pr")).rejects.toThrow(
      "duplicate eval task id",
    );
  });

  it("rejects malformed JSON before running an Agent", async () => {
    const directory = await mkdtemp(join(tmpdir(), "inalpha-eval-"));
    temporary.push(directory);
    await writeFile(join(directory, "broken.json"), "{not-json");

    await expect(loadGoldenTasks(directory, "pr")).rejects.toThrow(
      "invalid eval fixture",
    );
  });
});
