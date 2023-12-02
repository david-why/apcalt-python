from typing import TypeVar

from quart.typing import RouteCallable

__all__ = ['allow_anonymous']

CallableT = TypeVar('CallableT', bound=RouteCallable)


def allow_anonymous(func: CallableT) -> CallableT:
    func.__allow_anonymous__ = True
    return func
