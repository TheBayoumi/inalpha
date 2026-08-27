# Inalpha Research · 多视角研究与三方辩论

`services/research` 是 FastAPI 研究服务（`:8003`）。`POST /deep_dive` 先并行运行核心
analysts，再在观点存在分歧时触发 bull / bear / risk 辩论，最后由 manager 生成结构化、
可回放的 `ResearchPlan`。

## 当前链路

```text
DeepDiveRequest
  → 预取 bars + factor snapshot
  → technical / fundamental / sentiment / risk / macro / valuation 并行
  → 可选 Buffett / Lynch / Wood / Burry / Druckenmiller / Marks 人格
  → 有分歧时 bull → bear → risk，支持软早停与总超时
  → manager 综合 briefs + debate log
  → ResearchPlan（factors / signals / strategy_hint / trigger / stop_reason）
```

- 单个 analyst 失败不会抹掉其他视角，失败 brief 会明确标记后交给 manager 综合。
- `as_of` 是严格研究截止点；返回值保留 briefs、辩论轮次、触发与停止原因供审计。
- 数据来自 `services/data`，当前有效因子来自 `services/factor`；JWT 沿调用链透传。
- 当前 research service 读取部署级 `LLM_PROVIDER` / `LLM_MODEL` 与对应 provider key；
  per-owner Dashboard key 尚未透传到本服务，部署者需把这一限制视为当前多租户边界。

## HTTP API

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/health` | 服务与 provider 探活 |
| `POST` | `/deep_dive` | 执行完整研究链路，返回 `ResearchPlan` |

## 本地开发

```bash
cd services/research
uv sync --group dev
uv run uvicorn inalpha_research.main:app --reload --port 8003

uv run ruff check .
uv run pytest                       # 默认 fake LLM，不产生调用费用
```

真实模型测试会产生费用，只应在显式设置 provider/key 并主动运行 integration 标记时执行。
