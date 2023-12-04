from functools import wraps
from typing import Awaitable, Callable, ParamSpec, TypeVar, cast

from quart import current_app
from quart.typing import RouteCallable

from .sessions import BaseSessionInterface

__all__ = ['allow_anonymous', 'cached']

T = TypeVar('T')
P = ParamSpec('P')
CallableT = TypeVar('CallableT', bound=Callable[..., Awaitable])
RouteCallableT = TypeVar('RouteCallableT', bound=RouteCallable)


def allow_anonymous(func: RouteCallableT) -> RouteCallableT:
    func.__allow_anonymous__ = True
    return func


def cached(
    key_func: Callable[..., str], expiry: int | None = None
) -> Callable[[CallableT], CallableT]:
    def decorator(func: CallableT) -> CallableT:
        @wraps(func)
        async def inner(self, *args, **kwargs):
            cache_key = key_func(self, *args, **kwargs)
            cache = cast(BaseSessionInterface, current_app.session_interface)
            cached = await cache.get(cache_key, current_app)
            if cached is not None:
                return cached
            result = await func(self, *args, **kwargs)
            await cache.set(cache_key, result, current_app, expiry)
            return result

        return cast(CallableT, inner)

    return decorator
