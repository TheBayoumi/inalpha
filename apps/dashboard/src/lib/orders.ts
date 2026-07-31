import type { OrderRecord } from "@/lib/types";

/** 返回新数组，按订单事件时间与稳定 ID 倒序。 */
export function sortOrdersNewestFirst(orders: OrderRecord[]): OrderRecord[] {
  return [...orders].sort((left, right) => {
    const byTime = Date.parse(right.ts_event) - Date.parse(left.ts_event);
    return byTime || right.client_order_id.localeCompare(left.client_order_id);
  });
}
