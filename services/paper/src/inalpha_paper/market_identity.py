"""paper 交易入口的 market identity 规范化。"""
from __future__ import annotations

LEGACY_A_SHARE_VENUE = "akshare"
A_SHARE_VENUE = "baostock"
_A_SHARE_PREFIXES = frozenset({"sh", "sz"})


def canonicalize_market_identity(venue: str, symbol: str) -> tuple[str, str]:
    """返回与 data-service 一致的 canonical ``(venue, symbol)``。"""
    normalized_venue = venue.strip().lower()
    normalized_symbol = _canonicalize_a_share_symbol(symbol)
    if normalized_symbol is not None and normalized_venue in {
        LEGACY_A_SHARE_VENUE,
        A_SHARE_VENUE,
    }:
        return A_SHARE_VENUE, normalized_symbol
    return normalized_venue, symbol.strip()


def a_share_identity_variants(
    venue: str,
    symbol: str,
) -> tuple[str, str, str] | None:
    """返回 canonical identity 与另一种前后缀 symbol；非 A 股返回 ``None``。"""
    normalized_venue = venue.strip().lower()
    normalized_symbol = _canonicalize_a_share_symbol(symbol)
    if normalized_venue not in {LEGACY_A_SHARE_VENUE, A_SHARE_VENUE}:
        return None
    if normalized_symbol is None:
        return None
    prefix, code = normalized_symbol.split(".", 1)
    return A_SHARE_VENUE, normalized_symbol, f"{code}.{prefix}"


def _canonicalize_a_share_symbol(symbol: str) -> str | None:
    """把 ``SH.600519`` / ``600519.SH`` 归一为 ``sh.600519``。"""
    normalized = symbol.strip()
    if "." not in normalized:
        return None

    prefix, code = normalized.split(".", 1)
    if prefix.lower() in _A_SHARE_PREFIXES and code.isdigit() and len(code) == 6:
        return f"{prefix.lower()}.{code}"

    code, suffix = normalized.rsplit(".", 1)
    if suffix.lower() in _A_SHARE_PREFIXES and code.isdigit() and len(code) == 6:
        return f"{suffix.lower()}.{code}"
    return None
