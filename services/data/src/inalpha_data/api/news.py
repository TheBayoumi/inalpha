"""``GET /news`` —— 统一多市场财经新闻与官方披露。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from inalpha_shared.auth import User, get_current_user
from inalpha_shared.errors import InalphaError, ValidationError

from ..connectors.news import get_router
from ..news_models import NewsQuery, NewsResponse
from ..venues import canonicalize_market_identity

router = APIRouter(tags=["news"])
_SUPPORTED_MARKETS = {
    "au", "br", "ca", "cn", "crypto", "de", "fr", "global", "hk", "in", "jp", "kr", "uk", "us"
}
_SUPPORTED_LEGACY_VENUES = {"yfinance", "baostock", "akshare"}


class NewsScopeNotSupportedError(InalphaError):
    """查询有效，但没有 provider 覆盖该 scope。"""

    code = "NEWS_SCOPE_NOT_SUPPORTED"
    status_code = 422


@router.get("/news", response_model=NewsResponse)
async def get_news(
    _user: Annotated[User, Depends(get_current_user)],
    query: Annotated[NewsQuery, Query()],
) -> NewsResponse:
    """按市场和标的聚合新闻；旧 ``venue + symbol`` 请求保持兼容。"""
    if query.market and query.market not in _SUPPORTED_MARKETS:
        raise ValidationError(
            f"news market {query.market!r} not supported",
            code="NEWS_MARKET_NOT_SUPPORTED",
            details={"market": query.market, "supported": sorted(_SUPPORTED_MARKETS)},
        )
    requested_venue = query.venue
    requested_symbol = query.symbol
    if not query.market and query.symbol and not query.venue:
        query = query.model_copy(update={"venue": "yfinance"})
        requested_venue = "yfinance"
    if query.venue and query.symbol:
        venue, symbol = canonicalize_market_identity(query.venue, query.symbol)
        query = query.model_copy(update={"venue": venue, "symbol": symbol})
    if not query.market and query.venue not in _SUPPORTED_LEGACY_VENUES:
        raise ValidationError(
            f"news venue {query.venue!r} not supported",
            code="NEWS_VENUE_NOT_SUPPORTED",
            details={"venue": query.venue, "supported": sorted(_SUPPORTED_LEGACY_VENUES)},
        )
    news_router = get_router()
    if not news_router.has_coverage(query):
        raise NewsScopeNotSupportedError(
            "no news provider covers the requested scope",
            details={
                "market": query.market,
                "venue": query.venue,
                "symbol": query.symbol,
                "kinds": query.kinds,
                "language": query.language,
            },
        )
    response = await news_router.fetch(query)
    return response.model_copy(
        update={"venue": requested_venue, "symbol": requested_symbol}
    )
