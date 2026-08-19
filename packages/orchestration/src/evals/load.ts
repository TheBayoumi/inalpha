import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";

import { EvalFailureError } from "./errors.js";
import { GoldenTaskSchema, type EvalSuite, type GoldenTask } from "./schema.js";

/** 从目录读取、校验并按 suite 过滤版本化 Golden Tasks。 */
export async function loadGoldenTasks(
  directory: string,
  suite: EvalSuite,
): Promise<GoldenTask[]> {
  const names = (await readdir(directory))
    .filter((name) => name.endsWith(".json"))
    .sort();
  const tasks: GoldenTask[] = [];
  const ids = new Set<string>();
  for (const name of names) {
    const path = join(directory, name);
    let raw: unknown;
    try {
      raw = JSON.parse(await readFile(path, "utf8"));
    } catch (error) {
      throw new EvalFailureError(
        "fixture_invalid",
        `invalid eval fixture ${name}: ${messageOf(error)}`,
      );
    }
    const parsed = GoldenTaskSchema.safeParse(raw);
    if (!parsed.success) {
      throw new EvalFailureError(
        "fixture_invalid",
        `invalid eval fixture ${name}: ${parsed.error.message}`,
      );
    }
    if (ids.has(parsed.data.id)) {
      throw new EvalFailureError(
        "fixture_invalid",
        `duplicate eval task id: ${parsed.data.id}`,
      );
    }
    ids.add(parsed.data.id);
    if (parsed.data.suites.includes(suite)) tasks.push(parsed.data);
  }
  if (tasks.length === 0) {
    throw new EvalFailureError(
      "fixture_invalid",
      `no eval tasks found for suite: ${suite}`,
    );
  }
  return tasks;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
