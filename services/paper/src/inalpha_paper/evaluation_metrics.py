"""策略评估共用的 fitness 与 holdout 指标。"""
from __future__ import annotations

import logging
from typing import Any

from .engine.metrics import bar_returns, max_drawdown_pct, sharpe_ratio
from .engine.robustness import bootstrap_sharpe_ci
from .schemas import ValidationBlock, ValidationSegment
from .strategy_authoring import FitnessInputs, calmar_from_report, compose_fitness

logger = logging.getLogger(__name__)


def fitness_from_report(report: Any, *, bars_per_year: float) -> float:
    """按 paper 的多目标口径计算单次回测 fitness。"""
    calmar = calmar_from_report(
        total_return_pct=report.total_return_pct,
        max_drawdown_pct=report.max_drawdown_pct,
        num_bars_processed=report.num_bars_processed,
        bars_per_year=bars_per_year,
    )
    return compose_fitness(
        FitnessInputs(
            sharpe=report.sharpe,
            calmar=calmar,
            max_drawdown_pct=report.max_drawdown_pct,
            num_trades=report.num_trades,
            num_bars_processed=report.num_bars_processed,
        )
    )


def validation_from_report(
    report: Any,
    *,
    split: float,
    bars_per_year: float,
) -> ValidationBlock | None:
    """把单次回测曲线按时间切为 train/holdout 两段。"""
    curve: list[tuple[int, float]] = report.equity_curve
    if len(curve) < 10:
        return None
    split_idx = int(len(curve) * split)
    if split_idx < 2 or len(curve) - split_idx < 2:
        return None

    cut_ts_ns = curve[split_idx][0]
    values = [equity for _ts, equity in curve]
    train_values = values[:split_idx]
    holdout_values = values[split_idx - 1 :]
    fills = list(getattr(report, "fills", []) or [])
    train_fills = sum(1 for fill in fills if fill.ts_ns < cut_ts_ns)
    holdout_fills = len(fills) - train_fills

    def segment(
        segment_values: list[float],
        num_trades: int,
        *,
        bar_count: int | None = None,
    ) -> ValidationSegment:
        returns = bar_returns(segment_values)
        return ValidationSegment(
            sharpe=sharpe_ratio(returns, int(bars_per_year)),
            total_return_pct=(
                (segment_values[-1] / segment_values[0] - 1.0) * 100.0
                if segment_values[0] > 0
                else 0.0
            ),
            max_drawdown_pct=max_drawdown_pct(segment_values),
            num_trades=num_trades,
            num_bars=bar_count if bar_count is not None else len(segment_values),
        )

    train = segment(train_values, train_fills)
    holdout = segment(
        holdout_values,
        holdout_fills,
        bar_count=len(holdout_values) - 1,
    )
    flags: list[str] = []
    if holdout.num_bars < 30 or holdout.num_trades < 2 or report.num_trades < 5:
        flags.append("insufficient_sample")

    decay_ratio: float | None = None
    if train.sharpe is None or holdout.sharpe is None:
        flags.append("sharpe_undefined")
    elif train.sharpe <= 0:
        flags.append("train_sharpe_nonpositive")
    else:
        decay_ratio = holdout.sharpe / train.sharpe

    ci_includes_zero: bool | None = None
    holdout_returns = bar_returns(holdout_values)
    if len(holdout_returns) >= 30:
        try:
            ci_includes_zero = bootstrap_sharpe_ci(
                holdout_returns,
                n_samples=1000,
            ).ci_includes_zero
        except Exception:
            logger.warning("bootstrap_sharpe_ci failed", exc_info=True)

    return ValidationBlock(
        split_ratio=split,
        train=train,
        holdout=holdout,
        decay_ratio=decay_ratio,
        holdout_sharpe_ci_includes_zero=ci_includes_zero,
        flags=flags,
    )


__all__ = ["fitness_from_report", "validation_from_report"]
