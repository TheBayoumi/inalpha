import { describe, expect, it } from "vitest";

import { ScriptedModel } from "../../src/evals/scripted-model.js";

describe("ScriptedModel", () => {
  it("emits AI SDK v2 tool-call content", async () => {
    const model = new ScriptedModel("model-test", [
      { type: "tool-call", call: { tool: "lookup", input: { symbol: "AAPL" } } },
    ]);
    const result = await model.doGenerate({});

    expect(result.finishReason).toBe("tool-calls");
    expect(result.content).toEqual([
      {
        type: "tool-call",
        toolCallId: "eval-call-0-0",
        toolName: "lookup",
        input: '{"symbol":"AAPL"}',
      },
    ]);
    model.assertConsumed();
  });

  it("emits the complete v2 text stream lifecycle", async () => {
    const model = new ScriptedModel("model-test", [
      { type: "text", text: "final answer" },
    ]);
    const { stream } = await model.doStream({});
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);

    expect(chunks.map((chunk) => (chunk as { type: string }).type)).toEqual([
      "stream-start",
      "response-metadata",
      "text-start",
      "text-delta",
      "text-end",
      "finish",
    ]);
    model.assertConsumed();
  });

  it("fails on extra or unconsumed model calls", async () => {
    const extra = new ScriptedModel("extra", [{ type: "text", text: "done" }]);
    await extra.doGenerate({});
    await expect(extra.doGenerate({})).rejects.toThrow("unexpected extra call");

    const unconsumed = new ScriptedModel("unconsumed", [
      { type: "text", text: "one" },
      { type: "text", text: "two" },
    ]);
    await unconsumed.doGenerate({});
    expect(() => unconsumed.assertConsumed()).toThrow("unconsumed turn");
  });
});
