"""可持久化的策略评估快照。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .schemas import ValidationBlock


class EvaluationSnapshot(BaseModel):
    """稳定且精简的回测结果 DTO，不携带持仓、成交和完整权益曲线。"""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["e1.report.v1"] = "e1.report.v1"
    fitness: float
    annualization_periods: float
    initial_cash: float
    final_equity: float
    total_return_pct: float
    num_trades: int
    total_fees: float
    num_bars: int
    period_start: datetime | None
    period_end: datetime | None
    sharpe: float | None
    sortino: float | None
    calmar: float | None
    max_drawdown_pct: float
    win_rate: float | None
    annualized_return_pct: float | None
    annualized_volatility_pct: float | None
    profit_factor: float | None
    payoff_ratio: float | None
    expectancy: float | None
    exposure_pct: float | None
    protective_exits: int
    blew_up: bool
    health_warnings: list[str] = Field(default_factory=list, max_length=20)
    sharpe_ci_lower: float | None
    sharpe_ci_upper: float | None
    sharpe_ci_includes_zero: bool | None
    validation: ValidationBlock | None

    @classmethod
    def from_report(
        cls,
        report: Any,
        *,
        fitness: float,
        annualization_periods: float,
        validation: ValidationBlock | None,
    ) -> EvaluationSnapshot:
        """把引擎内部报告转成 JSON-safe 快照。"""
        warnings = [str(item)[:500] for item in report.health_warnings[:20]]
        return cls(
            fitness=fitness,
            annualization_periods=annualization_periods,
            initial_cash=report.initial_cash,
            final_equity=report.final_equity,
            total_return_pct=report.total_return_pct,
            num_trades=report.num_trades,
            total_fees=report.total_fees,
            num_bars=report.num_bars_processed,
            period_start=report.period_start,
            period_end=report.period_end,
            sharpe=report.sharpe,
            sortino=report.sortino,
            calmar=report.calmar,
            max_drawdown_pct=report.max_drawdown_pct,
            win_rate=report.win_rate,
            annualized_return_pct=report.annualized_return_pct,
            annualized_volatility_pct=report.annualized_volatility_pct,
            profit_factor=report.profit_factor,
            payoff_ratio=report.payoff_ratio,
            expectancy=report.expectancy,
            exposure_pct=report.exposure_pct,
            protective_exits=report.protective_exits,
            blew_up=report.blew_up,
            health_warnings=warnings,
            sharpe_ci_lower=report.sharpe_ci_lower,
            sharpe_ci_upper=report.sharpe_ci_upper,
            sharpe_ci_includes_zero=report.sharpe_ci_includes_zero,
            validation=validation,
        )


__all__ = ["EvaluationSnapshot"]
