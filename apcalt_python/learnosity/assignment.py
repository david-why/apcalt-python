import asyncio
import json
import time
from copy import deepcopy
from typing import Any, Self

from quart import current_app

from ..decorator import cached
from ..exceptions import BusinessError
from ..request import USER_AGENT
from ..request import get_session as _sess
from .request import make_signed_request


def _dumps(data):
    return json.dumps(data, separators=(',', ':'))


class Assignment:
    __slots__ = 'data', '_cache'

    def __init__(self, data):
        self.data = data
        self._cache = {}

    @property
    def _security(self):
        data = self.data['data']['apiActivity']['questionsApiActivity']
        return {
            'consumer_key': data['consumer_key'],
            'domain': 'apclassroom.collegeboard.org',
            'timestamp': data['timestamp'],
            'user_id': data['user_id'],
            'signature': data['signature'],
        }

    @cached(
        lambda self: f'qauth.{self.data["data"]["request"]["activity_id"]}'
        f'.{self.data["data"]["request"]["user_id"]}',
        60 * 30,
    )
    async def get_question_auth(self):
        sess = _sess()
        async with sess.post(
            'https://questions-va.learnosity.com/v2023.2.LTS/authenticate',
            data={
                'action': 'get',
                'security': _dumps(self._security),
                'usrequest': '{"metricsContext":["itemsapi","assessapi"]}',
            },
        ) as r:
            data = await r.json()
        return data['data']

    async def get_responses(self):
        if 'responses' in self._cache:
            exp, data = self._cache['responses']
            if exp > time.time():
                return deepcopy(data)
        sess = _sess()
        auth_data = await self.get_question_auth()
        cid = auth_data['id']
        security = self._security
        security_s = _dumps(security)
        user_id = security['user_id']
        prefix = f'{cid}_{user_id}_'
        activity = self.data['data']['apiActivity']['questionsApiActivity']
        response_ids = [prefix + q['response_id'] for q in activity['questions']]
        usrequest = {
            'questionResponseIds': response_ids,
            'questionSource': 'raw',
            'metricsContext': ['itemsapi', 'assessapi'],
        }
        async with sess.post(
            'https://questions-va.learnosity.com/v2022.1.LTS/questionresponses',
            data={
                'action': 'get',
                'security': security_s,
                'usrequest': _dumps(usrequest),
            },
        ) as r:
            data = await r.json()
        self._cache['responses'] = (time.time() + 5, data['data'])
        return data['data']

    async def set_responses(self, responses: list[dict[str, Any]]):
        sess = _sess()
        auth_data = await self.get_question_auth()
        prev_responses = await self.get_responses()
        cid = auth_data['id']
        security = self._security
        security_s = _dumps(security)
        user_id = security['user_id']
        prefix = f'{cid}_{user_id}_'
        qresponses = []
        for response in responses:
            prev_response = self._find_response(prev_responses, response['id'])
            new_response = self._convert_response(response['response'])
            if prev_response is None and new_response is None:
                continue
            if prev_response and new_response.get('value') == prev_response.get(
                'value'
            ):
                continue
            if prev_response and prev_response.get('revision') is not None:
                prev_revision = prev_response['revision']
                if isinstance(new_response, dict):
                    new_response['revision'] = prev_revision + 1
            qresponses.append({'id': prefix + response['id'], 'response': new_response})
        activity = self.data['data']['apiActivity']['questionsApiActivity']
        usrequest = {
            'submit': False,
            'state': activity['state'],
            'user_id': activity['user_id'],
            'activity_id': activity['id'],
            'activity_name': activity['name'],
            'course_id': 'none',
            'session_id': activity['session_id'],
            'metadata': await self._get_responses_metadata(),
            'init_metadata': {
                'id': '18ada422-9aa4-4654-9fa4-80c559873fbb',
                'time': int(time.time()),
                'deviceTime': False,
            },
            'questionResponses': qresponses,
            'metricsContext': ['itemsapi', 'assessapi'],
        }
        async with sess.post(
            'https://questions-va.learnosity.com/v2022.1.LTS/questionresponses',
            data={
                'action': 'update',
                'security': security_s,
                'usrequest': _dumps(usrequest),
            },
        ) as r:
            data = await r.json()
        return data['meta']['status']

    async def submit(self):
        sess = _sess()
        auth_data = await self.get_question_auth()
        cid = auth_data['id']
        security = self._security
        security_s = _dumps(security)
        user_id = security['user_id']
        prefix = f'{cid}_{user_id}_'
        activity = self.data['data']['apiActivity']['questionsApiActivity']
        response_ids = [prefix + q['response_id'] for q in activity['questions']]
        usrequest = {
            'submit': True,
            'state': activity['state'],
            'user_id': activity['user_id'],
            'activity_id': activity['id'],
            'activity_name': activity['name'],
            'course_id': 'none',
            'session_id': activity['session_id'],
            'metadata': await self._get_responses_metadata(),
            'init_metadata': {
                'id': '18ada422-9aa4-4654-9fa4-80c559873fbb',
                'time': int(time.time()),
                'deviceTime': False,
            },
            'questionResponses': [],
            'questionResponseIdsForReScore': response_ids,
            'metricsContext': ['itemsapi', 'assessapi'],
        }
        async with sess.post(
            'https://questions-va.learnosity.com/v2022.1.LTS/questionresponses',
            data={
                'action': 'update',
                'security': security_s,
                'usrequest': _dumps(usrequest),
            },
        ) as r:
            data = await r.json()
        return data['meta']['status']

    def _convert_response(self, response: Any):
        value = response
        if isinstance(response, dict) and 'value' in response:
            value = response['value']
        if isinstance(value, str):
            response = {'value': value, 'wordCount': value.count(' '), 'type': 'string'}
        elif isinstance(value, list):
            response = {'value': value, 'type': 'array'}
        elif isinstance(value, dict):
            response = {'value': value}
        if isinstance(response, dict):
            response.setdefault('apiVersion', 'v2.181.16')
            response.setdefault('revision', 1)
        return response

    def _find_response(self, responses: list, response_id: str, additional: list = []):
        for response in additional:
            if response['id'].split('_', 2)[2] == response_id:
                return response['response']
        for response in responses:
            if response['response_id'] == response_id:
                return response['response']

    async def _get_responses_metadata(self, additional: list = []):
        responses = await self.get_responses()
        data = self.data['data']
        items = []
        for item in data['apiActivity']['items']:
            question = item['questions'][0]
            response = self._find_response(
                responses, question['response_id'], additional
            )
            attempted = response and response.get('value')
            meta_item = {
                'reference': item['reference'],
                'source': item.get('source'),
                'time': 0,
                'response_ids': item['response_ids'],
                'user_flagged': False,
                'attempt_status': 'fully_attempted' if attempted else 'not_attempted',
            }
            items.append(meta_item)
        return {
            'items_api_version': 'v1.118.3',
            'custom_session_metadata': {
                'session_tags': [{'type': 'attempt_number', 'name': '-1'}]
            },
            'existing_session': False,
            'current_time': 0,
            'current_reading_time': False,
            'max_time': 0,
            'current_item_reference': data['apiActivity']['items'][0]['reference'],
            'current_sheet_position': 0,
            'items': items,
            'features': {},
            'session_start': True,
            'user_agent': USER_AGENT,
        }

    async def _ensure_set_responses(self):
        sess = _sess()
        auth_data = await self.get_question_auth()
        cid = auth_data['id']
        security = self._security
        security_s = _dumps(security)
        user_id = security['user_id']
        prefix = f'{cid}_{user_id}_'
        questions = self.data['data']['apiActivity']['questionsApiActivity'][
            'questions'
        ]
        response_ids = [prefix + q['response_id'] for q in questions]
        usrequest = {
            'questionResponseIds': response_ids,
            'questionSource': 'raw',
            'metricsContext': ['itemsapi', 'assessapi'],
        }
        async with sess.post(
            'https://questions-va.learnosity.com/v2022.1.LTS/questionresponses',
            data={
                'action': 'get',
                'security': security_s,
                'usrequest': _dumps(usrequest),
            },
        ) as r:
            data = await r.json()
        new_ids = [
            q['id'].split('_', 2)[2] for q in data['data'] if q.get('error') == 10005
        ]
        if not new_ids:
            return
        questions = {q['response_id']: q for q in questions}
        responses = []
        for response_id in new_ids:
            question = questions[response_id]
            responses.append(
                {
                    'id': prefix + response_id,
                    'type': question['type'],
                    'response_id': response_id,
                    'user_id': user_id,
                    'question': question,
                }
            )
        usrequest = {
            'questionResponses': responses,
            'metricsContext': ['itemsapi', 'assessapi'],
        }
        async with sess.post(
            'https://questions-va.learnosity.com/v2022.1.LTS/questionresponses',
            data={
                'action': 'set',
                'security': security_s,
                'usrequest': _dumps(usrequest),
            },
        ) as r:
            data = await r.json()
        if not data['meta']['status']:
            current_app.logger.error('Failed to set questionResponses: %s', data)
            raise BusinessError('Failed to set questionResponses')

    @classmethod
    async def from_signed_request(
        cls, signed_request: dict[str, Any], ensure_set: bool = True
    ) -> Self:
        data = await make_signed_request(
            signed_request, 'https://items-va.learnosity.com/v2022.1.LTS/activity'
        )
        assignment = cls(data)
        if ensure_set:
            await assignment._ensure_set_responses()
        return assignment
