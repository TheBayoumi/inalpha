import { describe, expect, it } from "vitest";

import type { OrderRecord } from "./types";
import { sortOrdersNewestFirst } from "./orders";

function order(clientOrderId: string, tsEvent: string): OrderRecord {
  return {
    client_order_id: clientOrderId,
    venue: "binance",
    symbol: "BTC/USDT",
    side: "BUY",
    type: "MARKET",
    quantity: 1,
    price: null,
    status: "FILLED",
    filled_quantity: 1,
    avg_fill_price: 100,
    fee: 0,
    notional: 100,
    realized_pnl: 0,
    ts_event: tsEvent,
    ts_init: tsEvent,
    trade_plan_id: null,
    strategy_run_id: "00000000-0000-0000-0000-000000000001",
  };
}

describe("sortOrdersNewestFirst", () => {
  it("sorts by event time descending without mutating the payload", () => {
    const oldest = order("order-a", "2026-07-29T08:00:00Z");
    const newest = order("order-b", "2026-07-31T08:00:00Z");
    const middle = order("order-c", "2026-07-30T08:00:00Z");
    const input = [oldest, newest, middle];

    expect(sortOrdersNewestFirst(input).map((value) => value.client_order_id)).toEqual([
      "order-b",
      "order-c",
      "order-a",
    ]);
    expect(input).toEqual([oldest, newest, middle]);
  });
});
