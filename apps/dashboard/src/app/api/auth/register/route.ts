import { NextResponse } from "next/server";

import { BackendError, backendFetch } from "@/lib/backend";

import { PublicJsonError, readLimitedJson } from "../request-json";

/**
 * 公开注册申请 BFF。
 *
 * 功能：把表单透传给内网 paper 的 waitlist 注册端点。
 * 何时用：未登录访客申请试用时。
 * 何时不用：创建已批准账号或管理员改密仍走受控 CLI。
 * 坑：后端对重复邮箱返回同一 202，前端不得据此判断邮箱是否存在。
 */
export async function POST(req: Request): Promise<Response> {
  let body: unknown;
  try {
    body = await readLimitedJson(req);
  } catch (error) {
    const status = error instanceof PublicJsonError ? error.status : 400;
    return NextResponse.json({ error: "INVALID_REQUEST" }, { status });
  }

  try {
    await backendFetch("paper", "/auth/register", {
      auth: false,
      method: "POST",
      body,
      timeoutMs: 15_000,
    });
    return NextResponse.json({ accepted: true }, { status: 202 });
  } catch (err) {
    if (err instanceof BackendError && err.status === 400) {
      return NextResponse.json({ error: "INVALID_APPLICATION" }, { status: 400 });
    }
    if (err instanceof BackendError && err.status === 422) {
      return NextResponse.json({ error: "INVALID_APPLICATION" }, { status: 400 });
    }
    if (err instanceof BackendError && err.status === 429) {
      return NextResponse.json({ error: "RATE_LIMITED" }, { status: 429 });
    }
    return NextResponse.json({ error: "SERVICE_UNAVAILABLE" }, { status: 502 });
  }
}
