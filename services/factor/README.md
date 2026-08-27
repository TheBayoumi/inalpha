# Inalpha Factor · 因子库与有效性闭环

`services/factor` 是独立 FastAPI 因子服务（`:8004`）。它只计算、验证和版本化信号，不下单。

## 当前能力

- 79 个系统因子，来源覆盖 pandas-ta、Alpha101、qlib Alpha158 风格与 FRED 宏观。
- `/compute`、`/score`、`/snapshot`：计算因子、IC/Rank IC 有效性与当前时点快照。
- `/panel/score`、`/backtest/score`：截面与回测样本评分。
- `/custom/score`：在受限表达式 DSL 中验证自定义因子。
- `/candidates`：owner-scoped 因子提案、列表和人工 review；不会自动注册候选。
- 血缘、去相关、衰减状态与 freshness 进入快照，供 Research 与 Paper 消费。

核心目录：`adapters/` 负责因子源，`engine.py` / `effectiveness.py` 负责计算与有效性，
`expression.py` 负责受限 DSL，`storage/` 负责候选持久化。

## 本地开发

```bash
cd services/factor
uv sync
uv run uvicorn inalpha_factor.main:app --reload --port 8004

uv run ruff check .
uv run pytest
```

配置统一读取仓库根 `.env`。宏观因子需要 `FRED_API_KEY`，不配置时价量因子仍正常工作。
