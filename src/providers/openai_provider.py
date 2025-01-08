import logging
from openai import OpenAI
from src.history import History
from src.providers.response_models import Action, RedditReply, RedditSubmission
from src.providers.base_provider import BaseProvider
from src.pydantic_models.openai_config import OpenAIConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
	def __init__(self, config: OpenAIConfig):
		self._client = OpenAI(api_key=config.api_key)
		self._model = config.model_id

	def generate_submission(self, system_prompt: str, prompt: str) -> RedditSubmission | None:
		completion = self._client.beta.chat.completions.parse(
		    model=self._model,
		    messages=[
		        {
		            "role": 'system',
		            "content": system_prompt
		        },
		        {
		            "role": 'user',
		            "content": prompt
		        },
		    ],
		    response_format=RedditSubmission,
		)
		return completion.choices[0].message.parsed

	def generate_comment(self, system_prompt: str, prompt: str) -> RedditReply | None:
		completion = self._client.beta.chat.completions.parse(
		    model=self._model,
		    messages=[
		        {
		            "role": 'system',
		            "content": system_prompt
		        },
		        {
		            "role": 'user',
		            "content": prompt
		        },
		    ],
		    response_format=RedditReply,
		)
		return completion.choices[0].message.parsed

	def get_action(self, system_prompt: str, initial_prompt: str, history: History) -> Action | None:
		messages = []
		messages.append({"role": 'system', "content": system_prompt})
		messages.append({"role": 'user', "content": initial_prompt})
		for turn in history.turns:
			messages.append({"role": 'assistant', "content": turn.model_action})
			messages.append({"role": 'user', "content": turn.action_result})

		for message in messages:
			logger.debug(f" -- {message['role']}: {message['content']}")

		completion = self._client.beta.chat.completions.parse(
		    model=self._model,
		    messages=messages,
		    response_format=Action,
		)
		return completion.choices[0].message.parsed
