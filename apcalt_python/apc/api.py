from math import ceil
from typing import TYPE_CHECKING, Any

from ..log import get_logger as _logger
from ..request import get_session as _sess

if TYPE_CHECKING:
    from .auth import APCAuth


class APClassroom:
    __slots__ = ('_auth',)

    def __init__(self, auth: 'APCAuth') -> None:
        self._auth = auth

    async def _gql(
        self,
        operation: str,
        query: str,
        variables: dict[str, Any] | None = None,
        endpoint: str = 'fym',
    ) -> Any:
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
        return resp['data'][operation]

    async def get_subjects(self) -> Any:
        return await self._gql(
            'studentSubjects', 'query studentSubjects{studentSubjects{id name}}'
        )

    async def get_outline(self, subject_id: str) -> Any:
        return await self._gql(
            'courseOutline',
            'query courseOutline($s:String){courseOutline(subjectId:$s){id:subjectId educationPeriod units{unitId:id displayName title description number instructionalPeriods examWeighting resources{...resourceFields __typename} subunits{subunitId:id displayName number displayNumber iconName resources{...resourceFields __typename}}}}} fragment resourceFields on Resource{id:uid resourceId:id displayName description icon ... on URLResource {url fileSize contentType} ... on SourceResource{url fileSize contentType} ... on YoutubeResource{url fileSize} ... on EmbeddedVideoResource{fileSize url videoId thumbnailUrl} ... on AssessmentResource{assessmentId resourceTypeDetails} ... on StudentPracticeResource{assessmentId} ... on GroupResource{description url} ... on PracticeQuestionsResource{questions{index accNum title libraryId subjectId itemId hasAllTopicsCovered type}}}',
            {'s': subject_id},
            'units',
        )

    async def finish_video(self, video_url, video_id) -> bool:
        cb_person_id = self._auth.data['account']['import_id']
        user_id = self._auth.data['account']['id']
        sess = await _sess()
        async with sess.get(
            'https://fast.wistia.com/embed/medias/%s.json' % video_url
        ) as r:
            media = await r.json()
        duration = ceil(media['media']['duration'])
        progress = [1] * duration
        ok = await self._gql(
            'storeDailyVideoProgress',
            'mutation storeDailyVideoProgress($u:Int,$v:Int,$c:String,$p:String) {storeDailyVideoProgress(userId:$u,videoId:$v,status:\"COMPLETE\",cbPersonid:$c,progress:$p,watchedPercentage:\"1.00\",playTimePercentage:\"0.0\"){ok}}',
            {'u': user_id, 'v': video_id, 'c': cb_person_id, 'p': progress},
        )
        return ok is not None and ok.get('ok', False)
