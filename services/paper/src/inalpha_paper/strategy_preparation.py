"""临时策略源码的审计、加载与契约准备。"""

from __future__ import annotations

from dataclasses import dataclass

from inalpha_shared.errors import ValidationError

from .strategy_authoring import (
    ContractError,
    DynamicLoadError,
    audit_strategy_code,
    load_strategy_class,
    verify_strategy_contract,
)


@dataclass(frozen=True, slots=True)
class PreparedStrategy:
    """通过审计、加载与契约校验的源码快照。"""

    source_code: str
    class_name: str


def audit_strategy_source(source_code: str) -> str:
    """只执行不会加载或运行候选代码的 AST 静态审计。"""
    audit = audit_strategy_code(source_code)
    if not audit.ok:
        raise ValidationError(
            f"strategy source failed audit: {audit.reason()}",
            code="CANDIDATE_REAUDIT_FAILED",
        )
    return source_code


def prepare_strategy_source(source_code: str) -> PreparedStrategy:
    """执行源码审计、受限加载和策略契约校验。"""
    audit_strategy_source(source_code)
    try:
        strategy_cls = load_strategy_class(source_code)
    except DynamicLoadError as exc:
        raise ValidationError(
            f"strategy source failed to load: {exc}",
            code="CANDIDATE_LOAD_FAILED",
        ) from exc
    try:
        verify_strategy_contract(strategy_cls)
    except ContractError as exc:
        raise ValidationError(
            f"strategy source failed contract check: {exc}",
            code="CANDIDATE_CONTRACT_FAILED",
        ) from exc
    return PreparedStrategy(source_code=source_code, class_name=strategy_cls.__name__)


__all__ = ["PreparedStrategy", "audit_strategy_source", "prepare_strategy_source"]
