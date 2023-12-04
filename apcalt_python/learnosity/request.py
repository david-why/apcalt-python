import json
from typing import Any

from ..request import get_session as _sess

__all__ = ['make_signed_request']


def _dumps(data):
    return json.dumps(data, separators=(',', ':'))


async def make_signed_request(signed_request: dict[str, Any], url: str):
    security = _dumps(signed_request['security'])
    request = _dumps(signed_request['request'])
    sess = _sess()
    async with sess.post(
        url, data={'action': 'get', 'security': security, 'request': request}
    ) as r:
        data = await r.json()
    return data
