import uuid
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar, cast

from quart import Response, g, request, session
from quart.typing import RouteCallable, ResponseReturnValue

from apcalt_python.apc.auth import APCAuth

from .decorator import allow_anonymous
from .exceptions import BusinessError
from .log import get_logger as _logger

CallableT = TypeVar('CallableT', bound=RouteCallable)
AsyncRouteCallable = Callable[..., Awaitable[ResponseReturnValue]]

__all__ = ['ROUTES']

ROUTES = []


def _route(rule: str, **kwargs: Any) -> Callable[[CallableT], CallableT]:
    def decorator(view_func: CallableT) -> CallableT:
        ROUTES.append({'rule': rule, 'view_func': view_func, **kwargs})
        return view_func

    return decorator


def _flag(
    fail_msg: str | None = None, fail_code: int = 500
) -> Callable[[Callable[..., Awaitable[Any]]], AsyncRouteCallable]:
    def decorator(func: Callable[..., Awaitable[Any]]) -> AsyncRouteCallable:
        @wraps(func)
        async def inner(*args, **kwargs):
            res = await func(*args, **kwargs)
            if not isinstance(res, bool):
                return res
            if res:
                return {'code': 200}
            raise BusinessError(fail_msg, fail_code)

        return inner

    return decorator


async def _auth() -> APCAuth:
    if 'auth' not in g:
        raise BusinessError('Please login first', 401)
    auth: APCAuth = g.auth
    try:
        await auth.ensure_account()
    except BusinessError as e:
        if e.code == 401:
            try:
                await auth.logout()
            except:
                pass
            del g.auth
        raise
    return auth


@_route('/ping')
@allow_anonymous
async def ping():
    return 'pong'


@_route('/auth/login', methods=['POST'])
@allow_anonymous
async def auth_login():
    data = cast(dict, await request.json)
    username = data['username']
    password = data['password']
    auth = APCAuth()
    await auth.login(username, password)
    g.auth = auth
    return str(uuid.uuid4())


@_route('/auth/logout')
async def auth_logout():
    if 'auth' in g:
        auth: APCAuth = g.auth
        await auth.logout()
        del g.auth
    return {'code': 200}


@_route('/auth/me')
async def auth_me():
    auth = await _auth()
    return auth.data


@_route('/subjects')
async def subjects():
    auth = await _auth()
    return await auth.api.get_subjects()


@_route('/subjects/<id>/courseOutline')
async def subject_outline(id: str):
    auth = await _auth()
    return await auth.api.get_outline(id)


@_route('/subjects/<id>/videos/<url>:<vid>/finish', methods=['POST'])
@_flag('Failed to finish video')
async def subject_video_finish(id: str, url: str, vid: str):
    auth = await _auth()
    return await auth.api.finish_video(url, vid)


@_route('/media/signedUrl', methods=['POST'])
async def media_signed_url():
    data = await request.json
    bucket = data['bucket']
    key = data['key']
    auth = await _auth()
    return await auth.api.get_signed_url(bucket, key)


@_route('/subjects/<subject_id>/assignments')
async def subject_assignments(subject_id: str):
    auth = await _auth()
    status = request.args.get('status', 'assigned')
    return await auth.api.list_assignments(subject_id, status)


@_route('/subjects/<subject_id>/assignments/<id>/start', methods=['POST'])
@_flag('Failed to start assignment')
async def assignment_start(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.start_assignment(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/raw')
async def assignment_raw(subject_id: str, id: str):
    auth = await _auth()
    assignment = await auth.api.get_assignment_raw(subject_id, id)
    return assignment.data


@_route('/subjects/<subject_id>/assignments/<id>')
async def assignment(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_assignment(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/responses/raw')
async def assignment_responses_raw(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_assignment_responses_raw(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/responses', methods=['GET'])
async def assignment_responses(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_assignment_responses(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/timed')
async def assignment_timed(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_assignment_timed(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/responses', methods=['PUT'])
@_flag('Failed to save responses')
async def assignment_responses_put(subject_id: str, id: str):
    auth = await _auth()
    responses = await request.json
    return await auth.api.set_assignment_responses(subject_id, id, responses)


@_route('/subjects/<subject_id>/assignments/<id>/submit', methods=['POST'])
@_flag('Failed to submit assignment')
async def assignment_submit(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.submit_assignment(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/review/raw')
async def assignment_review_raw(subject_id: str, id: str):
    auth = await _auth()
    assignment = await auth.api.get_assignment_review_raw(subject_id, id)
    return assignment.data


@_route('/subjects/<subject_id>/assignments/<id>/review')
async def assignment_review(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_assignment_review(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/review/responses/raw')
async def assignment_review_responses_raw(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_assignment_review_responses_raw(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/review/responses')
async def assignment_review_responses(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_assignment_review_responses(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/review/report')
async def assignment_review_report(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_assignment_review_report(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/review/answers')
async def assignment_review_answers(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_assignment_review_answers(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/scoring/gql')
async def scoring_gql(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_scoring_gql(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/scoring/raw')
async def scoring_raw(subject_id: str, id: str):
    auth = await _auth()
    assignment = await auth.api.get_scoring_raw(subject_id, id)
    return assignment.data


@_route('/subjects/<subject_id>/assignments/<id>/scoring')
async def scoring(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_scoring(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/scoring/responses/raw')
async def scoring_responses_raw(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_scoring_responses_raw(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/scoring/responses')
async def scoring_responses(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_scoring_responses(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/scoring/categories')
async def scoring_categories(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_scoring_categories(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/scoring/rubric/raw')
async def scoring_rubric_raw(subject_id: str, id: str):
    auth = await _auth()
    assignment = await auth.api.get_scoring_rubric_raw(subject_id, id)
    return assignment.data


@_route('/subjects/<subject_id>/assignments/<id>/scoring/rubric')
async def scoring_rubric(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_scoring_rubric(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/scoring/rubric/responses/raw')
async def scoring_rubric_responses_raw(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_scoring_rubric_responses_raw(subject_id, id)


@_route('/subjects/<subject_id>/assignments/<id>/scoring/rubric/responses')
async def scoring_rubric_responses(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.get_scoring_rubric_responses(subject_id, id)


@_route(
    '/subjects/<subject_id>/assignments/<id>/scoring/rubric/responses', methods=['PUT']
)
@_flag('Failed to save responses')
async def scoring_rubric_responses_put(subject_id: str, id: str):
    auth = await _auth()
    responses = await request.json
    return await auth.api.set_scoring_rubric_responses(subject_id, id, responses)


@_route('/subjects/<subject_id>/assignments/<id>/scoring/submit', methods=['POST'])
@_flag('Failed to submit scoring')
async def submit_scoring(subject_id: str, id: str):
    auth = await _auth()
    return await auth.api.submit_scoring(subject_id, id)


@_route('/health')
@allow_anonymous
async def health():
    return Response(status=200)


@_route('/test')
@allow_anonymous
async def test():
    session.setdefault('cnt', 0)
    session['cnt'] += 1
    return {'count': session['cnt']}
