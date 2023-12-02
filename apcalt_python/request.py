from aiohttp import ClientSession

__all__ = ['get_session']

SESSION: ClientSession = None  # type: ignore

async def get_session():
    global SESSION
    if SESSION is None:
        SESSION = ClientSession()
    return SESSION
