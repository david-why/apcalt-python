import uuid
from datetime import datetime, timezone
from typing import Any, Callable, TypedDict, TypeVar, cast

import aiohttp
from flask import current_app, request, session
from yarl import URL

from apcalt_python.exceptions import BusinessError

CallableT = TypeVar('CallableT', bound=Callable)

__all__ = ['ROUTES']

USER_AGENT = (
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'
)
HEADERS = {'User-Agent': USER_AGENT}

ROUTES = []


def _logger():
    return current_app.logger


def route(rule: str, **kwargs: Any):
    def decorator(view_func: CallableT) -> CallableT:
        ROUTES.append({'rule': rule, 'view_func': view_func, **kwargs})
        return view_func

    return decorator


class LoginData(TypedDict):
    cb_login: str
    cb_user_name: str
    aws_expire: datetime
    account: dict | None


async def _ensure_account(data: LoginData):
    await _ensure_aws(data)
    if data['account'] is not None and datetime.fromisoformat(
        data['account']['expires']
    ).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        return
    async with aiohttp.ClientSession(headers=HEADERS) as sess:
        async with sess.post(
            'https://am-accounts-production.collegeboard.org/account/api/',
            json={
                'namespace': 'st',
                'sessionId': data['cb_login'],
                'username': data['cb_user_name'],
            },
        ) as r:
            if r.status == 400:
                raise BusinessError('Failed to get APC token, please login again', 401)
            account = await r.json()
    data['account'] = account


async def _ensure_aws(data: LoginData):
    if (
        data['cb_user_name']
        and data['aws_expire']
        and data['aws_expire'] > datetime.now(timezone.utc)
    ):
        return
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(
            'https://sucred.catapult-prod.collegeboard.org/rel/temp-user-aws-creds',
            headers={'Authorization': 'CBLogin ' + data['cb_login']},
            params={
                'cbEnv': 'pine',
                'appId': '366',
                'cbAWSDomains': 'apfym,catapult',
                'cacheNonce': 0,
            },
        ) as r:
            creds = await r.json()
    if r.status == 400:
        error_type = creds.get('errorType')
        if error_type == 'SucredProviderError':
            raise BusinessError('Refresh AWS gives error, please login again', 401)
    if r.status != 200:
        _logger().error('Error received from AWS refresh: %s', creds)
        raise BusinessError('Refresh AWS failed')
    data['cb_user_name'] = creds['cbUserProfile']['sessionInfo']['identityKey'][
        'userName'
    ]
    data['aws_expire'] = datetime.fromisoformat(
        creds['catapult']['Credentials']['Expiration'][:-1]
    ).replace(tzinfo=timezone.utc)


@route('/auth/login', methods=['POST'])
async def auth_login():
    data = cast(dict, request.json)
    username = data['username']
    password = data['password']
    login_data: LoginData = {
        'cb_login': '',
        'cb_user_name': '',
        'aws_expire': datetime.now(timezone.utc),
        'account': None,
    }
    async with aiohttp.ClientSession(headers=HEADERS) as sess:
        async with sess.get(
            'https://account.collegeboard.org/login/login?appId=366&idp=ECL&DURL=https://myap.collegeboard.org/login'
        ) as r:
            t = await r.text()
        if r.status == 403:
            _logger().error('Login returned 403, is this IP address banned?: %s', t)
            raise BusinessError('Cannot login to APC')
        if '"stateToken":' not in t:
            _logger().error('State token not found: %s', t)
        start_idx = t.index('"stateToken":') + 14
        end_idx = t.index('"', start_idx)
        state_token = t[start_idx:end_idx]
        while r'\x' in state_token:
            idx = state_token.index(r'\x')
            c = chr(int(state_token[idx + 2 : idx + 4], 16))
            state_token = state_token[:idx] + c + state_token[idx + 4 :]
        async with sess.post(
            'https://prod.idp.collegeboard.org/api/v1/authn',
            json={
                'username': username,
                'password': password,
                'stateToken': state_token,
                'options': {
                    'warnBeforePasswordExpired': False,
                    'multiOptionalFactorEnroll': False,
                },
            },
        ) as r:
            authn = await r.json()
        if 'next' not in authn['_links']:
            _logger().error('No next link in authn response: %s', authn)
            raise BusinessError('Failed to login to APC')
        next_link = authn['_links']['next']['href']
        async with sess.get(next_link) as r:
            t = await r.text()
        cookies = sess.cookie_jar.filter_cookies(URL('https://www.collegeboard.org'))
        if 'cb_login' not in cookies:
            _logger().error('No cb_login cookie found: %s: %s', cookies, t)
        login_data['cb_login'] = cookies['cb_login'].value
    await _ensure_aws(login_data)
    session['login_data'] = login_data
    return str(uuid.uuid4())


async def _login_data():
    if 'login_data' not in session:
        raise BusinessError('Please login first', 401)
    login_data = session['login_data']
    await _ensure_account(login_data)
    return login_data


@route('/auth/logout')
def auth_logout():
    if 'login_data' in session:
        del session['login_data']
    return {'code': 200}


@route('/auth/me')
async def auth_me():
    return await _login_data()


@route('/test')
def test():
    session.setdefault('count', 0)
    session['count'] += 1
    if session['count'] > 20:
        session['count'] = 0
        raise BusinessError('too many times', 400)
    return session['count']
