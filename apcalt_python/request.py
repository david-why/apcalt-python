from aiohttp import ClientSession

__all__ = ['get_session']

USER_AGENT = (
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'
)
HEADERS = {'User-Agent': USER_AGENT}

SESSION: ClientSession = None  # type: ignore

def get_session():
    global SESSION
    if SESSION is None:
        SESSION = ClientSession(headers=HEADERS)
    return SESSION
