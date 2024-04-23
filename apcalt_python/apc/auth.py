from datetime import datetime, timezone
from typing import Any, TypedDict

from aiohttp import ClientSession
from yarl import URL

from ..exceptions import BusinessError
from ..log import get_logger as _logger
from ..request import HEADERS, get_session
from .api import APClassroom


class LoginData(TypedDict):
    cb_login: str
    cb_user_name: str
    aws_expire: datetime
    account: Any


class APCAuth:
    __slots__ = ('data', 'modified')

    @staticmethod
    def _default_data() -> LoginData:
        return {
            'cb_login': '',
            'cb_user_name': '',
            'aws_expire': datetime.now(timezone.utc),
            'account': None,
        }

    def __init__(self):
        self.data = self._default_data()
        self.modified = False

    @property
    def user_id(self):
        return self.data['account']['id']

    async def login(self, username: str, password: str):
        self.data.update(self._default_data())
        self.modified = True
        async with ClientSession(headers=HEADERS) as sess:
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
            self.data['cb_login'] = cookies['cb_login'].value
        await self.ensure_aws()

    async def logout(self):
        self.data.update(self._default_data())
        self.modified = True

    async def ensure_aws(self):
        if (
            self.data['cb_user_name']
            and self.data['aws_expire']
            and self.data['aws_expire'] > datetime.now(timezone.utc)
        ):
            return
        session = get_session()
        async with session.get(
            'https://sucred.catapult-prod.collegeboard.org/rel/temp-user-aws-creds',
            headers={'Authorization': 'CBLogin ' + self.data['cb_login']},
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
        self.data['cb_user_name'] = creds['cbUserProfile']['sessionInfo'][
            'identityKey'
        ]['userName']
        self.data['aws_expire'] = datetime.fromisoformat(
            creds['catapult']['Credentials']['Expiration'][:-1]
        ).replace(tzinfo=timezone.utc)
        self.modified = True

    async def ensure_account(self):
        await self.ensure_aws()
        if self.data['account'] is not None and datetime.fromisoformat(
            self.data['account']['expires']
        ).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            return
        sess = get_session()
        async with sess.post(
            'https://am-accounts-production.collegeboard.org/account/api/',
            json={
                'namespace': 'st',
                'sessionId': self.data['cb_login'],
                'username': self.data['cb_user_name'],
            },
        ) as r:
            if r.status == 400:
                raise BusinessError('Failed to get APC token, please login again', 401)
            account = await r.json()
        self.data['account'] = account
        self.modified = True

    async def access_token(self):
        await self.ensure_account()
        return self.data['account']['access_token']

    @property
    def api(self):
        return APClassroom(self)
