import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

/**
 * 管理员待审列表 BFF。
 *
 * 功能：读取 paper 中的 pending 用户。
 * 何时用：管理员打开 waitlist 页面时。
 * 何时不用：普通用户查询自己的申请状态；登录接口会给出该状态。
 * 坑：权限必须由 paper 查询数据库角色判定，不能只信 session 或前端菜单。
 */
export async function GET(): Promise<Response> {
  try {
    const result = await backendFetch<{ users: unknown[] }>("paper", "/auth/waitlist");
    return NextResponse.json(result);
  } catch (err) {
    const status =
      typeof err === "object" && err !== null && "status" in err
        ? (err as { status?: unknown }).status
        : undefined;
    if (status === 401 || status === 403) {
      return NextResponse.json({ error: "FORBIDDEN" }, { status: 403 });
    }
    return NextResponse.json({ error: "SERVICE_UNAVAILABLE" }, { status: 502 });
  }
}
