# Inalpha Data · 多市场数据服务

`services/data` 是 FastAPI 数据接入层（`:8001`）：统一查询与缓存行情、财报、新闻、市场
概览、成分股、汇率和永续合约数据，并把 bars/ticks 写入 PostgreSQL + TimescaleDB。

## 当前能力

- **多市场路由**：Binance / CCXT（crypto）、akshare / BaoStock（A股、港股）、
  yfinance / Alpaca（美股与全球单股、指数）、FRED（宏观）。
- **行情与时序**：`/bars`、`/ticker`、`/backfill/bars`、`/symbols/search`，支持 freshness
  与本地缓存策略。
- **基本面与市场情报**：`/fundamentals`、`/news`、`/market/*`、`/constituents`。
- **Web 与跨资产辅助数据**：`/web/search`、`/web/news`、`/web/fetch`、`/fx`、
  `/perp/funding`。
- 除 `/health` 外的业务端点均要求用户 JWT；连接器失败按稳定错误码返回，不静默伪造数据。

关键目录：

| 目录 | 职责 |
|---|---|
| `connectors/` | 市场、新闻、搜索与基本面连接器 |
| `api/` | HTTP 路由、输入校验与错误映射 |
| `storage/` | bars 与指数成分等持久化 |
| `venues.py` | venue / symbol 能力与市场路由 |
| `scheduler.py` | 数据侧周期任务 |

## 本地开发

先按根 README 启动 `infra` Compose 并执行 Alembic migration，然后：

```bash
cd services/data
uv sync --group dev
uv run uvicorn inalpha_data.main:app --reload --port 8001

uv run ruff check .
uv run pytest
```

配置统一从仓库根 `.env` 读取。`DATABASE_URL` 与 `JWT_SECRET` 必填；Binance 公共行情无需
交易 key，FRED 宏观因子需要 `FRED_API_KEY`，其余付费或认证连接器只在配置存在时启用。
