import type { FullOutput } from "@mastra/core/stream";
import { describe, expect, it } from "vitest";

import {
  normalizeTrajectory,
  stableStringify,
} from "../../src/evals/trajectory.js";

function output(
  result?: { result: unknown; isError?: boolean },
): FullOutput {
  return {
    steps: [
      {
        toolCalls: [
          {
            payload: {
              toolCallId: "call-1",
              toolName: "fixture.read",
              args: { symbol: "AAPL" },
            },
          },
        ],
        toolResults: result === undefined
          ? []
          : [
              {
                payload: {
                  toolCallId: "call-1",
                  result: result.result,
                  isError: result.isError,
                },
              },
            ],
      },
    ],
  } as unknown as FullOutput;
}

describe("agent eval trajectory", () => {
  it("uses failed raw execution when a provider omits its tool result", () => {
    const trajectory = normalizeTrajectory(output(), [
      {
        tool: "fixture.read",
        input: { symbol: "AAPL" },
        status: "failed",
      },
    ]);

    expect(trajectory[0]).toMatchObject({
      attempted: true,
      executed: true,
      resultClass: "tool_error",
    });
  });

  it("classifies permission results without claiming raw execution", () => {
    const trajectory = normalizeTrajectory(
      output({ result: { deniedBy: "permission", isError: true } }),
      [],
    );

    expect(trajectory[0]).toMatchObject({
      executed: false,
      resultClass: "permission_deny",
    });
  });

  it("sorts keys and removes sensitive metadata", () => {
    expect(
      stableStringify({
        z: 1,
        nested: { password: "hidden", a: 2 },
        providerMetadata: { requestId: "unstable" },
      }),
    ).toBe(
      '{"nested":{"a":2,"password":"[REDACTED]"},' +
        '"providerMetadata":"[REDACTED]","z":1}',
    );
  });
});
