"""统一多市场财经新闻 connector。"""

from .router import NewsRouter, close_router, get_router, init_router

__all__ = ["NewsRouter", "close_router", "get_router", "init_router"]
