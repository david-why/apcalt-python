import uuid
from typing import Any, TypeVar, cast

from quart import g, request, session
from quart.typing import RouteCallable

from apcalt_python.apc.auth import APCAuth

from .exceptions import BusinessError
from .log import get_logger as _logger

CallableT = TypeVar('CallableT', bound=RouteCallable)

__all__ = ['ROUTES', 'LOGIN_WHITELIST']

USER_AGENT = (
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'
)
HEADERS = {'User-Agent': USER_AGENT}

ROUTES = []
LOGIN_WHITELIST = ['/auth/login', '/test']


def route(rule: str, **kwargs: Any):
    def decorator(view_func: CallableT) -> CallableT:
        ROUTES.append({'rule': rule, 'view_func': view_func, **kwargs})
        return view_func

    return decorator


async def _auth() -> APCAuth:
    if 'auth' not in g:
        raise BusinessError('Please login first', 401)
    auth: APCAuth = g.auth
    await auth.ensure_account()
    return auth


@route('/auth/login', methods=['POST'])
async def auth_login():
    data = cast(dict, await request.json)
    username = data['username']
    password = data['password']
    auth = APCAuth()
    await auth.login(username, password)
    g.auth = auth
    return str(uuid.uuid4())


@route('/auth/logout')
async def auth_logout():
    if 'auth' in g:
        auth: APCAuth = g.auth
        await auth.logout()
        del g.auth
    return {'code': 200}


@route('/auth/me')
async def auth_me():
    auth = await _auth()
    return auth.data


@route('/test')
async def test():
    session.setdefault('cnt', 0)
    session['cnt'] += 1
    return session['cnt']
