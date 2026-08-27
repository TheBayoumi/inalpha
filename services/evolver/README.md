# Inalpha Evolver · E1 策略演化生产闭环

`services/evolver` 是独立的 FastAPI 策略演化服务（`:8005`）。它冻结实验输入，调用当前
owner 授权的 LLM 生成 unified diff，在受限加载器和独立回测子进程中评估候选，并把 run、
slot、候选、费用与可复现元数据持久化到 PostgreSQL。

## 安全与产品边界

- 每次会产生 LLM 费用的 run 都需要绑定 `owner + operation_id + llm_config_digest` 的显式
  审批；审批 JWT 有效期 5 分钟，幂等键稳定标识同一操作。
- bars、数据 manifest/hash、种子源码、非密钥 LLM 配置和定价摘要在执行前冻结；baseline、
  seed 与候选使用同一份 frozen bars。
- 用户 LLM API key 只在执行时通过 Dashboard 内部路由按 owner/config_id 获取，不进入 run
  配置、候选记录或日志；队列只短暂保存 orchestration 签发的 capability，兑换后立即清除。
- 当前演化费用审批只为 `deepseek`、`openai`、`kimi`、`zhipu` 各自的默认模型维护冻结计价
  表；未知模型与其他 provider 均 fail closed。输入 UTF-8 字节数与输出 token 数也受冻结
  上限约束，因此 `budget × 最大单候选估算` 是执行硬边界。它们仍可用于普通对话。
- 演化运行只连接上述 provider 的官方 HTTPS API 端点；普通对话可用的自定义代理地址不会
  进入 Evolver，避免服务端凭据解析链路被用来访问内网地址。
- 所有 run/candidate 查询都按认证 owner 隔离；全局并发与单账户 active run 数均有限制。
- Evolver 只生成和评估候选，绝不会自动 promote、启动策略或下单。
- AST 审计、受限动态加载、契约检查和回测子进程是当前防线；子进程并非 hardened container
  或 VM，不应把未知代码当作已完成强隔离。

## 执行链路

```text
Dashboard / orchestration
  → 冻结 LLM + pricing snapshot，取得逐次审批
  → 签发 owner/operation/config/digest 绑定的 Ed25519 credential grant
  → POST /api/v1/runs（Idempotency-Key + 两个审批/凭据 header）
  → 冻结真实 bars + manifest/hash
  → 解析 seed，跑同数据 baseline
  → LLM 生成 unified diff
  → diff 应用 → AST/loader/contract 校验 → 子进程回测
  → fitness 排序，持久化 token/cost/失败原因
  → 用户显式选择后，另走 paper promote / start / plan-exec
```

核心目录：

| 目录 | 职责 |
|---|---|
| `api/` | run 创建/列表/详情、candidate 详情、abort、审批与幂等校验 |
| `data/` | bars 拉取、质量校验、冻结文件、manifest 与 hash |
| `governor/` | seed 解析和单代演化流程 |
| `mutator/` | owner-scoped LLM 客户端、prompt 与 unified-diff 应用 |
| `sandbox/` | 复用 paper 的 AST 审计、受限加载与 Strategy 契约检查 |
| `evaluator/` | frozen dataset 回测、子进程资源限制与 fitness |
| `runtime/` | 异步 dispatcher、slot 并发、取消、超时与终态收口 |
| `storage/` | PostgreSQL run/candidate 持久化与 owner-scoped 查询 |
| `owner_llm.py` | 转交短时、逐操作且同 scope 可重试的 credential grant，读取 owner 模型配置 |

## HTTP API

所有 `/api/v1/*` 端点都要求用户 JWT。

> `inalpha-evolver 0.2.0` 收紧了创建 run 的契约：`POST /api/v1/runs` 现在必须同时提供
> 冻结的 `llm` 快照、`Idempotency-Key`、`X-Evolution-Approval` 与
> `X-Evolution-Credential`。这是 0.x 阶段的安全性
> breaking change；自建部署应将 Dashboard、orchestration、migration 0041 与 Evolver
> 作为同一次升级发布，直接调用旧接口的客户端必须同步更新。

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/runs` | 创建或幂等复用 run，返回 `202`；额外要求审批与幂等 header |
| `GET` | `/api/v1/runs` | 分页列出当前 owner 的 run |
| `GET` | `/api/v1/runs/{run_id}` | 查看 run、slot 与候选摘要 |
| `GET` | `/api/v1/candidates/{candidate_id}` | 查看当前 owner 的候选代码、指标和审计结果 |
| `POST` | `/api/v1/runs/{run_id}/abort` | 请求取消 queued/running run |

编排层对应暴露 `evolver.run_evolution`、`evolver.get_evolution`、
`evolver.get_candidate`、`evolver.abort_evolution` 四个 tools。

## 配置与启动

主要环境变量统一放在仓库根 `.env`：

| 变量 | 用途 |
|---|---|
| `DATABASE_URL` | run/candidate 持久化 |
| `DATA_SERVICE_URL` | 获取并冻结真实 bars |
| `DASHBOARD_SERVICE_URL` | 即时读取 owner LLM 配置的内部服务地址 |
| `JWT_SECRET` / `JWT_ALGORITHM` | 用户与 service JWT 验证 |
| `EVOLVER_POOL_SIZE` | PostgreSQL 连接池大小 |
| `EVOLVER_MAX_RUNNING_RUNS` | 服务级同时运行上限 |
| `EVOLVER_ACCOUNT_ACTIVE_LIMIT` | 单 owner active run 上限 |
| `EVOLVER_QUEUE_TIMEOUT_S` | queued 最长等待（默认 24 小时，超时显式 abort；短于 grant 的 30 小时 TTL） |
| `EVOLVER_JOB_TIMEOUT_S` / `EVOLVER_RUN_TIMEOUT_S` | 单候选与整次 run 超时 |
| `EVOLVER_JOB_MEM_GB` | 回测子进程内存上限 |
| `EVOLVER_LLM_TIMEOUT_S` | 单次 LLM 变异超时 |

owner 凭据 capability 使用 Ed25519。生成 DER/base64 密钥：

```bash
openssl genpkey -algorithm ED25519 -out /tmp/inalpha-evolution-private.pem
openssl pkey -in /tmp/inalpha-evolution-private.pem -outform DER | base64 | tr -d '\n'
openssl pkey -in /tmp/inalpha-evolution-private.pem -pubout -outform DER | base64 | tr -d '\n'
```

依次填入 `EVOLUTION_CREDENTIAL_PRIVATE_KEY_B64` 与
`EVOLUTION_CREDENTIAL_PUBLIC_KEY_B64`。生产私钥只注入 orchestration；Dashboard 只持有公钥，
Evolver 显式移除私钥，因此不能自行签发任意 owner/config 的明文凭据读取授权。

```bash
cd infra/migrations && uv run alembic upgrade head && cd ../..
cd services/evolver
uv sync
uv run uvicorn inalpha_evolver.main:app --port 8005 --reload

uv run ruff check .
uv run pytest
```

仓库级开发推荐直接运行 `bash scripts/dev.sh`。下一阶段 E2 只先增加 best-parent 多代选择与
early stopping；MAP-Elites / Island Model 在拿到真实成功率、拒绝分布和费用样本后再评估。
