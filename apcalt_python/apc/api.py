import json
from math import ceil
from typing import TYPE_CHECKING, Any

from ..decorator import cached
from ..exceptions import BusinessError
from ..learnosity.assignment import Assignment
from ..learnosity.request import make_signed_request
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
        sess = _sess()
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
        user_id = self._auth.user_id
        sess = _sess()
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
        return ok is not None

    async def get_signed_url(self, bucket: str, key: str) -> str:
        sess = _sess()
        async with sess.post(
            'https://apc-api-production.collegeboard.org/fym/media/api/signed_url',
            json={'bucket': bucket, 'key': key, 'fail_if_key_is_missing': False},
            headers={'Authorization': 'Bearer ' + await self._auth.access_token()},
        ) as r:
            data = await r.json()
        return data['signedUrl']

    # ========== ASSIGNMENT STUFF ==========

    def _convert_assignment(self, assignment: Assignment):
        data = assignment.data
        activity = data['data']['apiActivity']
        items = []
        for item in activity['items']:
            questions = []
            shared_passage = None
            for feature in item['features']:
                if feature['type'] == 'sharedpassage':
                    shared_passage = feature['content']
            for question in item['questions']:
                qtype = question['type']
                options = None
                if question.get('options'):
                    options = []
                    for option in question['options']:
                        options.append(option)
                qdata = {
                    'responseId': question['response_id'],
                    'type': qtype,
                    'metadata': question['metadata'],
                    'stimulus': question['stimulus'],
                    'allowMultiple': question.get('multiple_responses', False),
                    'title': question.get('title'),
                }
                if shared_passage is not None:
                    qdata['sharedPassage'] = shared_passage
                if options is not None:
                    qdata['options'] = options
                questions.append(qdata)
            idata = {
                'reference': item['reference'],
                'metadata': item['metadata'],
                'questions': questions,
            }
            items.append(idata)
        title = '[Unknown title]'
        if activity.get('title'):
            title = activity['title']
        elif activity['questionsApiActivity'].get('title'):
            title = activity['questionsApiActivity']['title']
        return {'title': title, 'items': items}

    def _convert_responses(self, responses: Any):
        data = {}
        for response in responses:
            print(response)
            value = response.get('response') or {}
            if isinstance(value, str):
                value = json.loads(value)
            data[response['response_id']] = value.get('value')
        return data

    async def list_assignments(self, subject_id: str, status: str = 'assigned'):
        sess = _sess()
        async with sess.get(
            'https://apc-api-production.collegeboard.org/fym/assessments/api/chameleon/student_assignments/%s/?status=%s'
            % (subject_id, status),
            headers={'Authorization': 'Bearer ' + await self._auth.access_token()},
        ) as r:
            data = await r.json()
        if 'assignments' not in data:
            raise BusinessError('Subject not found', 404)
        return data['assignments']

    async def start_assignment(self, subject_id: str, id: str):
        data = await self._gql(
            'startAssignment',
            'mutation startAssignment($a:Int){startAssignment(assignmentId:$a,isImpersonating:false){ok}}',
            {'a': int(id)},
        )
        result = data is not None and data.get('ok', False)
        if not result:
            return False
        await self.get_assignment_raw(subject_id, id)
        return True

    @cached(lambda self, _, id: f'assignment.{id}.{self._auth.user_id}', 60 * 30)
    async def get_assignment_raw(self, subject_id: str, id: str):
        data = await self._gql(
            'assignmentPlayer',
            'query assignmentPlayer($a:String,$s:String){assignmentPlayer(assignmentId:$a,isImpersonating:false,subjectId:$s,config:\"{}\"){learnositySignedRequest}}',
            {'a': id, 's': subject_id},
        )
        if data is None or data.get('learnositySignedRequest') is None:
            raise BusinessError('Cannot get assignment items')
        signed_request = json.loads(data['learnositySignedRequest'])
        return await Assignment.from_signed_request(signed_request)

    async def get_assignment(self, subject_id: str, id: str):
        return self._convert_assignment(await self.get_assignment_raw(subject_id, id))

    async def get_assignment_responses_raw(self, subject_id: str, id: str):
        assignment = await self.get_assignment_raw(subject_id, id)
        return await assignment.get_responses()

    async def get_assignment_responses(self, subject_id: str, id: str):
        responses = await self.get_assignment_responses_raw(subject_id, id)
        return self._convert_responses(responses)

    async def get_assignment_timed(self, subject_id: str, id: str):
        data = await self._gql(
            'assignmentSession',
            'query assignmentSession($a:Int){assignmentSession(assignmentId:$a,isImpersonating:false){timedSession{timeElapsed totalTime submissionStatus}}}',
            {'a': int(id)},
        )
        return data['timedSession']

    async def set_assignment_responses(
        self, subject_id: str, id: str, responses: list[dict[str, Any]]
    ):
        assignment = await self.get_assignment_raw(subject_id, id)
        return await assignment.set_responses(responses)

    async def submit_assignment(self, subject_id: str, id: str):
        assignment = await self.get_assignment_raw(subject_id, id)
        ok = await assignment.submit()
        if not ok:
            raise BusinessError('Failed to submit leanosity assignment')
        data = await self._gql(
            'submitAssignment',
            'mutation submitAssignment($a:String){submitAssignment(assignmentId:$a){ok}}',
            {'a': id},
        )
        return data is not None and data.get('ok', False)

    @cached(lambda self, _, id: f'rassignment.{id}.{self._auth.user_id}', 60 * 30)
    async def get_assignment_review_raw(self, subject_id: str, id: str):
        data = await self._gql(
            'assignmentReview',
            'query assignmentReview($a:String,$s:String){assignmentReview(assignmentId:$a,studentId:$s,config:"{}",inline:true,showCorrectAnswers:true,scorerType:"teacher"){learnositySignedRequest}}',
            {'a': id, 's': str(self._auth.user_id)},
        )
        if data is None or data.get('learnositySignedRequest') is None:
            raise BusinessError('Cannot get assignment (review) items')
        signed_request = json.loads(data['learnositySignedRequest'])
        return await Assignment.from_signed_request(signed_request, ensure_set=False)

    async def get_assignment_review(self, subject_id: str, id: str):
        return self._convert_assignment(
            await self.get_assignment_review_raw(subject_id, id)
        )

    async def get_assignment_review_responses_raw(self, subject_id: str, id: str):
        assignment = await self.get_assignment_review_raw(subject_id, id)
        return await assignment.get_responses()

    async def get_assignment_review_responses(self, subject_id: str, id: str):
        responses = await self.get_assignment_review_responses_raw(subject_id, id)
        return self._convert_responses(responses)

    async def get_assignment_review_report(self, subject_id: str, id: str):
        data = await self._gql(
            'assignment',
            'query assignment($a:String,$s:String){assignment(assignmentId:$a){resultsByItem(studentId:$s)}}',
            {'a': id, 's': str(self._auth.user_id)},
        )
        signed_request = json.loads(data['resultsByItem'])
        report = await make_signed_request(
            signed_request, 'https://reports-va.learnosity.com/v2023.2.LTS/init'
        )
        report = report['data'][0]['data']
        for value in report.values():
            report = value['users']
            for value in report.values():
                return value['items']
        raise BusinessError('Failed to find report item')

    async def get_assignment_review_answers(self, subject_id: str, id: str):
        assignment = await self.get_assignment_review_raw(subject_id, id)
        activity = assignment.data['data']['apiActivity']
        answers = {}
        for item in activity['items']:
            for question in item['questions']:
                response_id = question['response_id']
                qtype = question['type']
                if qtype == 'mcq':
                    answers[response_id] = question['validation']['valid_response'][
                        'value'
                    ]
        return answers

    @cached(lambda self, _, id: f'scoregql.{id}.{self._auth.user_id}', 60 * 30)
    async def get_scoring_gql(self, subject_id: str, id: str):
        data = await self._gql(
            'assignmentScoringByRubric',
            'query assignmentScoringByRubric($u:String,$a:String){assignmentScoringByRubric(studentId:$u,assignmentId:$a,isImpersonating:false){studentSessionReviewSignedRequest scoringRubricSignedRequest rubricCategoryReferencesByQuestion}}',
            {'u': self._auth.user_id, 'a': id},
        )
        return data

    @cached(lambda self, _, id: f'sassignment.{id}.{self._auth.user_id}', 60 * 30)
    async def get_scoring_raw(self, subject_id: str, id: str):
        gql = await self.get_scoring_gql(subject_id, id)
        return await Assignment.from_signed_request(
            json.loads(gql['studentSessionReviewSignedRequest']), ensure_set=False
        )

    async def get_scoring(self, subject_id: str, id: str):
        return self._convert_assignment(await self.get_scoring_raw(subject_id, id))

    async def get_scoring_responses_raw(self, subject_id: str, id: str):
        assignment = await self.get_scoring_raw(subject_id, id)
        return await assignment.get_responses()

    async def get_scoring_responses(self, subject_id: str, id: str):
        responses = await self.get_scoring_responses_raw(subject_id, id)
        return self._convert_responses(responses)

    async def get_scoring_categories(self, subject_id: str, id: str):
        gql = await self.get_scoring_gql(subject_id, id)
        return json.loads(gql['rubricCategoryReferencesByQuestion'])

    @cached(lambda self, _, id: f'rubric.{id}.{self._auth.user_id}', 60 * 30)
    async def get_scoring_rubric_raw(self, subject_id: str, id: str):
        gql = await self.get_scoring_gql(subject_id, id)
        return await Assignment.from_signed_request(
            json.loads(gql['scoringRubricSignedRequest'])
        )

    async def get_scoring_rubric(self, subject_id: str, id: str):
        return self._convert_assignment(
            await self.get_scoring_rubric_raw(subject_id, id)
        )

    async def get_scoring_rubric_responses_raw(self, subject_id: str, id: str):
        assignment = await self.get_scoring_rubric_raw(subject_id, id)
        return await assignment.get_responses()

    async def get_scoring_rubric_responses(self, subject_id: str, id: str):
        responses = await self.get_scoring_rubric_responses_raw(subject_id, id)
        return self._convert_responses(responses)

    async def set_scoring_rubric_responses(
        self, subject_id: str, id: str, responses: list[dict[str, Any]]
    ):
        assignment = await self.get_scoring_rubric_raw(subject_id, id)
        return await assignment.set_responses(responses)

    async def submit_scoring(self, subject_id: str, id: str):
        assignment = await self.get_scoring(subject_id, id)
        categories = await self.get_scoring_categories(subject_id, id)
        rubric = await self.get_scoring_rubric(subject_id, id)
        responses = await self.get_scoring_rubric_responses(subject_id, id)
        scores = []
        for itemref, refs in categories.items():
            for item in assignment['items']:
                if item['reference'] == itemref:
                    break
            else:
                continue
            respid = item['questions'][0]['responseId']
            max_score = 0
            score = 0
            for ref in refs:
                for item in rubric['items']:
                    if item['reference'] == ref:
                        break
                else:
                    continue
                max_score += item['questions'][0]['options'][0]['max_score']
                score += int(
                    responses.get(item['questions'][0]['responseId'], {}).get(
                        'score', 0
                    )
                )
            scores.append(
                {
                    'response_id': respid,
                    'score': score,
                    'max_score': max_score,
                    'attempted': True,
                }
            )
        data = await self._gql(
            'updateScores',
            'mutation updateScores($a:String,$s:String,$c:String){updateScores(assignmentId:$a,studentId:$s,scores:$c,scoringCompleted:true){ok}}',
            {
                'a': id,
                's': self._auth.user_id,
                'c': json.dumps(scores, separators=(',', ':')),
            },
        )
        if data is None or not data.get('ok', False):
            raise BusinessError('Failed to update scores')
        rubricass = await self.get_scoring_rubric_raw(subject_id, id)
        return await rubricass.submit()
