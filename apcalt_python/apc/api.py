from typing import TYPE_CHECKING, Any

from ..request import get_session as _sess
from ..log import get_logger as _logger

if TYPE_CHECKING:
    from .auth import APCAuth


class APClassroom:
    __slots__ = ('_auth',)

    def __init__(self, auth: 'APCAuth'):
        self._auth = auth

    async def _gql(
        self,
        operation: str,
        query: str,
        variables: dict[str, Any] | None = None,
        endpoint: str = 'fym',
    ):
        data: dict[str, Any] = {'operationName': operation, 'query': query}
        if variables is not None:
            data['variables'] = variables
        sess = await _sess()
        async with sess.post(
            'https://apc-api-production.collegeboard.org/%s/graphql' % endpoint,
            json=data,
            headers={'Authorization': 'Bearer ' + await self._auth.access_token()},
        ) as r:
            resp = await r.json()
        if 'data' not in resp:
            _logger().error('GraphQL request (%s) failed. Response: %s', data, resp)
            raise ValueError('No data in GraphQL request: %s' % resp)
        return resp['data']
