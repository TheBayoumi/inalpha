import { NextResponse } from "next/server";

/** 将 paper 审核失败收敛为不泄露后端细节的稳定 BFF 错误契约。 */
export function reviewErrorResponse(error: unknown): Response {
  const status =
    typeof error === "object" && error !== null && "status" in error
      ? (error as { status?: unknown }).status
      : undefined;
  if (status === 401 || status === 403) {
    return NextResponse.json({ error: "FORBIDDEN" }, { status: 403 });
  }
  if (status === 409) {
    return NextResponse.json({ error: "ALREADY_REVIEWED" }, { status: 409 });
  }
  return NextResponse.json({ error: "SERVICE_UNAVAILABLE" }, { status: 502 });
}
