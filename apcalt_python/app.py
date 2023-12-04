import pickle
from datetime import timedelta
from importlib import resources
from typing import Any, cast

import redis.asyncio
from quart import Quart, abort, current_app, g, request, send_file, session
from quart.typing import ResponseReturnValue

from .decorator import allow_anonymous
from .exceptions import BusinessError
from .routes import ROUTES
from .sessions import Session

__all__ = ['build_app']


class CustomQuart(Quart):
    async def make_response(self, rv: ResponseReturnValue):
        if (
            isinstance(rv, (int, str, list))
            or isinstance(rv, dict)
            and 'code' not in rv
        ):
            rv = {'code': 200, 'data': rv}
        return await super().make_response(rv)


@allow_anonymous
async def _static_route(path: str):
    parts = path.split('/')
    for part in parts:
        if part.startswith('.') or part == '':
            abort(404)
    file = resources.files(__package__).joinpath('static').joinpath(path)
    if not file.is_file():
        abort(404)
    with resources.as_file(file) as real_file:
        return await send_file(real_file)


@allow_anonymous
async def _home_route():
    return await _static_route('index.html')


async def _error_handler(error: BusinessError):
    data: dict[str, Any] = {'code': error.code}
    if error.msg is not None:
        data['msg'] = error.msg
    return data, error.code


async def _before_request():
    endpoint = request.endpoint
    if endpoint is None:
        return
    view_func = current_app.view_functions.get(endpoint)
    if view_func is None:
        return
    if not getattr(view_func, '__allow_anonymous__', False) and 'auth' not in session:
        raise BusinessError('Please login first', 401)
    if 'auth' in session:
        g.auth = session['auth']


async def _after_request(response):
    if 'auth' in g and g.auth.modified:
        session['auth'] = g.auth
    return response


def build_app(
    name: str = __name__, extra_config: dict[str, Any] | None = None
) -> Quart:
    app = CustomQuart(name, static_folder=None)
    app.config.from_prefixed_env()
    if extra_config:
        app.config.update(extra_config)
    if app.config.get('SESSION_TYPE', 'null') == 'null':
        app.logger.warning(
            'The SESSION_TYPE config variable is set to "null". You might want to '
            'enable persistent sessions by changing its value, for example by setting '
            'the FLASK_SESSION_TYPE environment variable.'
        )
    if app.config.get('SESSION_TYPE') == 'redis' and app.config.get('SESSION_URI'):
        app.config['SESSION_REDIS'] = redis.asyncio.from_url(
            app.config['SESSION_URI'], encoding='utf-8', decode_responses=False
        )
    app.config.setdefault('PERMANENT_SESSION_LIFETIME', timedelta(days=30))
    # Session(app)
    Session(app)
    cast(Any, app.session_interface).serializer = pickle
    app.add_url_rule('/<path:path>', view_func=_static_route)
    app.add_url_rule('/', view_func=_home_route)
    for route in ROUTES:
        app.add_url_rule(**route)
    app.before_request(_before_request)
    app.after_request(_after_request)
    app.register_error_handler(BusinessError, _error_handler)
    return app
