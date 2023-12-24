import asyncio
import os
import pickle
import time
import uuid
from abc import ABCMeta, abstractmethod
from typing import Any, ClassVar, Protocol, Type

import aiofiles
from quart import Quart
from quart.sessions import SecureCookieSession, SessionInterface
from quart.sessions import SessionMixin
from quart.sessions import SessionMixin as SessionMixin
from quart.wrappers import BaseRequestWebsocket, Response
from quart.wrappers.response import Response as QuartResponse
from redis import asyncio as aioredis
from werkzeug.wrappers import Response as WerkzeugResponse
from werkzeug.wrappers.response import Response as WerkzeugResponse


class Session:
    _app: Quart | None

    def __init__(self, app: Quart | None = None):
        self._app = None
        if app is not None:
            self.init_app(app)

    @property
    def app(self):
        if self._app is None:
            raise RuntimeError(
                'You have not set an app object yet. Use `Session.init_app(app)` '
                'to set the app object before you use the session.'
            )

    def init_app(self, app: Quart):
        self._app = app

        config = self._app.config.copy()
        config.setdefault('SESSION_TYPE', 'null')
        config.setdefault('SESSION_COOKIE_NAME', 'session')
        config.setdefault('SESSION_KEY_PREFIX', 'session:')
        config.setdefault('SESSION_PERMANENT', True)
        config.setdefault('SESSION_REDIS', None)
        config.setdefault('SESSION_FILE_PATH', os.path.join(os.getcwd(), 'quart_store'))
        config.setdefault('SESSION_FILE_MODE', 384)

        session_type = config['SESSION_TYPE']
        session_interface = None
        interfaces: dict[str, Type[BaseSessionInterface]] = {
            'filesystem': FileSystemSessionInterface,
            'redis': RedisSessionInterface,
            'memory': MemorySessionInterface,
            'null': MemorySessionInterface,
        }
        if session_type in interfaces:
            session_interface = interfaces[session_type](config)
        else:
            raise ValueError(f'Unknown session type {session_type}')

        app.session_interface = session_interface  # type: ignore


class BaseSession(SecureCookieSession):
    def __init__(
        self,
        sid: str,
        initial: dict | None = None,
        permanent: bool = True,
    ):
        super().__init__(initial)
        self.sid = sid
        if permanent:
            self.permanent = permanent


class Serializer(Protocol):
    def loads(self, __data: bytes) -> Any:
        ...

    def dumps(self, __data: Any) -> bytes:
        ...


class BaseSessionInterface(SessionInterface):
    session_class: ClassVar[Type[BaseSession]]
    pickle_based: ClassVar[bool] = False

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    async def open_session(
        self, app: Quart, request: BaseRequestWebsocket
    ) -> SessionMixin | None:
        cname = self.config['SESSION_COOKIE_NAME']
        permanent = self.config['SESSION_PERMANENT']
        sid = request.cookies.get(cname)
        if not sid:
            sid = str(uuid.uuid4())
            return self.session_class(sid=sid, permanent=permanent)

        key_prefix = self.config['SESSION_KEY_PREFIX']
        key = key_prefix + sid
        value = await self.get(key, app)
        if value is None:
            sid = str(uuid.uuid4())
            return self.session_class(sid=sid, permanent=permanent)

        return self.session_class(sid, value)

    async def save_session(
        self,
        app: Quart,
        session: BaseSession,
        response: QuartResponse | WerkzeugResponse | None,
    ) -> None:
        if not session.modified or response is None:
            return

        cname = self.config['SESSION_COOKIE_NAME']
        key_prefix = self.config['SESSION_KEY_PREFIX']
        key = key_prefix + session.sid
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        if not session:
            if session.modified:
                await self.delete(key, app)
                response.delete_cookie(cname, domain=domain, path=path)
            return
        httponly = self.get_cookie_httponly(app)
        samesite = self.get_cookie_samesite(app)
        secure = self.get_cookie_secure(app)
        expires = self.get_expiration_time(app, session)

        await self.set(key, dict(session), app)
        response.set_cookie(
            cname,
            session.sid,
            expires=expires,
            httponly=httponly,
            domain=domain,
            path=path,
            secure=secure,
            samesite=samesite,
        )

    async def has(self, key: str, app: Quart) -> bool:
        raise NotImplementedError

    # should return dict[str, Any] for session keys
    async def get(self, key: str, app: Quart) -> Any:
        raise NotImplementedError

    # value will be dict[str, Any] for session keys
    async def set(
        self, key: str, value: Any, app: Quart, expiry: int | None = None
    ) -> None:
        raise NotImplementedError

    async def delete(self, key: str, app: Quart) -> None:
        raise NotImplementedError


class FileSystemSession(BaseSession):
    pass


class ExpiryData:
    __slots__ = ('expiry', 'data')

    def __init__(self, data: Any, expiry: float | None = None):
        self.expiry = expiry
        self.data = data

    @property
    def expired(self):
        return self.expiry is not None and self.expiry < time.time()


class FileSystemSessionInterface(BaseSessionInterface):
    session_class = FileSystemSession
    pickle_based = True

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        path = self.config['SESSION_FILE_PATH']
        os.makedirs(path, exist_ok=True)

    async def has(self, key: str, app: Quart) -> bool:
        fname = key.replace('/', '__') + '.bin'
        path = self.config['SESSION_FILE_PATH']
        file_path = os.path.join(path, fname)
        return os.path.isfile(file_path)

    async def get(self, key: str, app: Quart) -> Any:
        fname = key.replace('/', '__') + '.bin'
        path = self.config['SESSION_FILE_PATH']
        file_path = os.path.join(path, fname)
        if not os.path.isfile(file_path):
            return
        async with aiofiles.open(file_path, 'rb') as f:
            data = await f.read()
        try:
            expiry_data: ExpiryData = pickle.loads(data)
        except:
            await self.delete(key, app)
            return
        if expiry_data.expired:
            await self.delete(key, app)
            return
        return expiry_data.data

    async def set(
        self, key: str, value: Any, app: Quart, expiry: int | None = None
    ) -> None:
        fname = key.replace('/', '__') + '.bin'
        path = self.config['SESSION_FILE_PATH']
        file_path = os.path.join(path, fname)
        expiry_data = ExpiryData(value, expiry)
        data = pickle.dumps(expiry_data)
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(data)

    async def delete(self, key: str, app: Quart) -> None:
        fname = key.replace('/', '__') + '.bin'
        path = self.config['SESSION_FILE_PATH']
        file_path = os.path.join(path, fname)
        if os.path.isfile(file_path):
            os.unlink(file_path)


class RedisSession(BaseSession):
    pass


class RedisSessionInterface(BaseSessionInterface):
    session_class = RedisSession
    pickle_based = True

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        redis: aioredis.Redis | None = config.get('SESSION_REDIS')
        if redis is None:
            uri = config.get('SESSION_URI', 'redis://localhost')
            redis = aioredis.from_url(uri, decode_responses=False)
        self.redis = redis

    async def has(self, key: str, app: Quart) -> bool:
        return bool(await self.redis.exists(key))

    async def get(self, key: str, app: Quart) -> Any:
        data = await self.redis.get(key)
        try:
            return pickle.loads(data)
        except:
            await self.delete(key, app)
            return

    async def set(
        self, key: str, value: Any, app: Quart, expiry: int | None = None
    ) -> None:
        data = pickle.dumps(value)
        await self.redis.set(key, data, expiry)

    async def delete(self, key: str, app: Quart) -> None:
        await self.redis.delete(key)


class MemorySession(BaseSession):
    pass


class MemorySessionInterface(BaseSessionInterface):
    session_class = RedisSession

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._storage: dict[str, ExpiryData] = {}

    def _check_expiry(self):
        for key in frozenset(self._storage):
            value = self._storage[key]
            if value.expired:
                del self._storage[key]

    async def has(self, key: str, app: Quart):
        return key in self._storage

    async def get(self, key: str, app: Quart):
        self._check_expiry()
        value = self._storage.get(key)
        if value is not None:
            return value.data

    async def set(
        self, key: str, value: Any, app: Quart, expiry: int | None = None
    ) -> None:
        self._check_expiry()
        expiry_data = ExpiryData(value, expiry)
        self._storage[key] = expiry_data

    async def delete(self, key: str, app: Quart) -> None:
        if key in self._storage:
            del self._storage[key]
