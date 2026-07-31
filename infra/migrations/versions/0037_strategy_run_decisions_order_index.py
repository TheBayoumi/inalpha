"""为订单查询增加模拟盘 run 反向引用索引。

订单与模拟盘通过 strategy_run_decisions.order_id 软关联。组合总览需要从最近订单跳转到
对应 run；部分索引避免订单列表对不断增长的决策表做全表扫描。
"""
from __future__ import annotations

from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """给非空 order_id 建立反向引用索引。"""
    op.execute(
        "CREATE INDEX strategy_run_decisions_order_idx "
        "ON strategy_run_decisions (order_id) WHERE order_id IS NOT NULL"
    )


def downgrade() -> None:
    """删除订单反向引用索引。"""
    op.execute("DROP INDEX IF EXISTS strategy_run_decisions_order_idx")
