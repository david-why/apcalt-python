from datetime import timedelta
from importlib import resources
from typing import Any

import redis
from asgiref.wsgi import WsgiToAsgi
from flask import Flask, Response, abort, g, request, send_file, session
from flask.typing import ResponseReturnValue
from flask_session import Session

from apcalt_python.exceptions import BusinessError

from .routes import LOGIN_WHITELIST, ROUTES

__all__ = ['build_app', 'build_asgi']


class CustomFlask(Flask):
    def make_response(self, rv: ResponseReturnValue) -> Response:
        if (
            isinstance(rv, (int, str, list))
            or isinstance(rv, dict)
            and 'code' not in rv
        ):
            rv = {'code': 200, 'data': rv}
        return super().make_response(rv)


def _static_route(path: str):
    parts = path.split('/')
    for part in parts:
        if part.startswith('.') or part == '':
            abort(404)
    file = resources.files(__package__).joinpath('static').joinpath(path)
    if not file.is_file():
        abort(404)
    with resources.as_file(file) as real_file:
        return send_file(real_file)


def _home_route():
    return _static_route('index.html')


def _error_handler(error: BusinessError):
    data: dict[str, Any] = {'code': error.code}
    if error.msg is not None:
        data['msg'] = error.msg
    return data, error.code


def _before_request():
    if request.path not in LOGIN_WHITELIST and 'auth' not in session:
        raise BusinessError('Please login first', 401)
    if 'auth' in session:
        g.auth = session['auth']


def _after_request(response):
    if 'auth' in g and g.auth.modified:
        session['auth'] = g.auth
    return response


def build_app(
    name: str = __name__, extra_config: dict[str, Any] | None = None
) -> Flask:
    app = CustomFlask(name, static_folder=None)
    app.config.from_prefixed_env()
    if extra_config:
        app.config.update(extra_config)
    if app.config.get('SESSION_TYPE', 'null') == 'null':
        app.logger.warning(
            'The SESSION_TYPE config variable is set to "null". You might want to '
            'enable persistent sessions by changing its value, for example by setting '
            'the FLASK_SESSION_TYPE environment variable.'
        )
    if app.config.get('SESSION_REDIS_URL'):
        app.config['SESSION_REDIS'] = redis.from_url(app.config['SESSION_REDIS_URL'])
    app.config.setdefault('PERMANENT_SESSION_LIFETIME', timedelta(days=30))
    Session(app)
    app.add_url_rule('/<path:path>', view_func=_static_route)
    app.add_url_rule('/', view_func=_home_route)
    for route in ROUTES:
        app.add_url_rule(**route)
    app.before_request(_before_request)
    app.after_request(_after_request)
    app.register_error_handler(BusinessError, _error_handler)
    return app


def build_asgi(name: str = __name__, extra_config: dict[str, Any] | None = None):
    app = build_app(name=name, extra_config=extra_config)
    return WsgiToAsgi(app)


if __name__ == '__main__':
    app = build_app()
