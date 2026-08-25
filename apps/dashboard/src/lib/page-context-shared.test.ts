import { describe, expect, it } from "vitest";

import {
  buildPageContextEnvelope,
  parsePageContext,
  stripPageContext,
} from "./page-context-shared";

const RUN_ID = "11111111-1111-4111-8111-111111111111";
const CANDIDATE_ID = "22222222-2222-4222-8222-222222222222";

describe("evolution page context", () => {
  it("解析列表、运行详情与候选详情", () => {
    expect(parsePageContext("/evolution")).toEqual({
      kind: "evolution_list",
      pathname: "/evolution",
    });
    expect(parsePageContext(`/evolution/${RUN_ID}`)).toEqual({
      kind: "evolution_run_detail",
      id: RUN_ID,
      pathname: `/evolution/${RUN_ID}`,
    });
    expect(parsePageContext(`/evolution/candidates/${CANDIDATE_ID}`)).toEqual({
      kind: "evolution_candidate_detail",
      id: CANDIDATE_ID,
      pathname: `/evolution/candidates/${CANDIDATE_ID}`,
    });
  });

  it("详情 envelope 使用演化专用 id 键", () => {
    expect(
      buildPageContextEnvelope({
        kind: "evolution_run_detail",
        id: RUN_ID,
        pathname: `/evolution/${RUN_ID}`,
      }),
    ).toContain(`evolution_run_id=${RUN_ID}`);
  });

  it("清除完整和被截断的上下文块", () => {
    expect(stripPageContext("<page_context>\npage=evolution_list\n</page_context>\n\nhello"))
      .toBe("hello");
    expect(stripPageContext("<page_context>\npage=evolution_run_detail")).toBe("");
  });
});
