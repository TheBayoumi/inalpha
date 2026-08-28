import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

import { PublicJsonError, readLimitedJson } from "../request-json";
import { activateErrorResponse } from "./activate-error";

/** 公开激活 BFF；一次性令牌换取密码设置，成功后账号才变为 active。 */
export async function POST(req: Request): Promise<Response> {
  let body: unknown;
  try {
    body = await readLimitedJson(req);
  } catch (error) {
    const status = error instanceof PublicJsonError ? error.status : 400;
    return NextResponse.json({ error: "INVALID_REQUEST" }, { status });
  }
  try {
    await backendFetch("paper", "/auth/activate", {
      auth: false,
      method: "POST",
      body,
      timeoutMs: 15_000,
    });
    return NextResponse.json({ activated: true });
  } catch (error) {
    return activateErrorResponse(error);
  }
}
