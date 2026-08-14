"""paper 交易入口的 market identity 规范化。"""
from __future__ import annotations

LEGACY_A_SHARE_VENUE = "akshare"
A_SHARE_VENUE = "baostock"
YFINANCE_VENUE = "yfinance"
_A_SHARE_PREFIXES = frozenset({"sh", "sz"})
_LEGACY_GLOBAL_PREFIX_TO_SUFFIX = {
    "hk": ".HK",
    "jp": ".T",
    "uk": ".L",
    "de": ".DE",
}


def canonicalize_market_identity(venue: str, symbol: str) -> tuple[str, str]:
    """返回与 data-service 一致的 canonical ``(venue, symbol)``。"""
    normalized_venue = venue.strip().lower()
    normalized_symbol = _canonicalize_a_share_symbol(symbol)
    if normalized_symbol is not None and normalized_venue in {
        LEGACY_A_SHARE_VENUE,
        A_SHARE_VENUE,
    }:
        return A_SHARE_VENUE, normalized_symbol
    if normalized_venue == LEGACY_A_SHARE_VENUE:
        global_symbol = _canonicalize_legacy_global_symbol(symbol)
        if global_symbol is not None:
            return YFINANCE_VENUE, global_symbol
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


def legacy_global_identity_variants(
    venue: str,
    symbol: str,
) -> tuple[str, str, str] | None:
    """返回 legacy ``akshare/<prefix>.<code>`` 对应的 yfinance identity。"""
    canonical_venue, canonical_symbol = canonicalize_market_identity(venue, symbol)
    if canonical_venue != YFINANCE_VENUE or "." not in canonical_symbol:
        return None
    code, suffix = canonical_symbol.rsplit(".", 1)
    suffix_with_dot = f".{suffix.upper()}"
    reverse = {value: key for key, value in _LEGACY_GLOBAL_PREFIX_TO_SUFFIX.items()}
    prefix = reverse.get(suffix_with_dot)
    if prefix is None:
        return None
    legacy_code = code.zfill(5) if prefix == "hk" else code
    return YFINANCE_VENUE, canonical_symbol, f"{prefix}.{legacy_code}"


def _canonicalize_legacy_global_symbol(symbol: str) -> str | None:
    """把 ``hk.00700`` 等历史 akshare 格式转换为 yfinance 后缀格式。"""
    normalized = symbol.strip()
    if "." not in normalized:
        return None
    prefix, code = normalized.split(".", 1)
    suffix = _LEGACY_GLOBAL_PREFIX_TO_SUFFIX.get(prefix.lower())
    if suffix is None or not code:
        return None
    if prefix.lower() == "hk":
        if not code.isdigit():
            return None
        code = code.lstrip("0").zfill(4)
    else:
        code = code.upper()
    return f"{code}{suffix}"


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
