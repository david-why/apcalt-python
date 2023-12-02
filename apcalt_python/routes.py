from typing import Any, Callable, TypeVar
from flask import session

from flask.typing import RouteCallable

from apcalt_python.exceptions import BusinessError

RouteCallableT = TypeVar('RouteCallableT', bound=RouteCallable)

__all__ = ['ROUTES']

ROUTES = []


def route(rule: str, **kwargs: Any):
    def decorator(view_func: RouteCallableT) -> RouteCallableT:
        ROUTES.append({'rule': rule, 'view_func': view_func, **kwargs})
        return view_func

    return decorator


@route('/test')
def test():
    session.setdefault('count', 0)
    session['count'] += 1
    if session['count'] > 20:
        session['count'] = 0
        raise BusinessError(400, 'too many times')
    return session['count']
