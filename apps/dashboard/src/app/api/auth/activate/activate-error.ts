import { NextResponse } from "next/server";

/** 将激活后端错误映射为稳定且不泄露内部细节的公开响应。 */
export function activateErrorResponse(error: unknown): Response {
  const status =
    typeof error === "object" && error !== null && "status" in error
      ? (error as { status?: unknown }).status
      : undefined;
  if (status === 400 || status === 422) {
    return NextResponse.json({ error: "INVALID_ACTIVATION" }, { status: 400 });
  }
  if (status === 409) {
    return NextResponse.json({ error: "ACTIVATION_USED" }, { status: 409 });
  }
  if (status === 429) {
    return NextResponse.json(
      { error: "ACTIVATION_BUSY" },
      { status: 429, headers: { "Retry-After": "5" } },
    );
  }
  return NextResponse.json({ error: "SERVICE_UNAVAILABLE" }, { status: 502 });
}
