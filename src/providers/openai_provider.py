import logging
from typing import List
from openai import OpenAI
from src.pydantic_models.agent_state import HistoryItem
from src.providers.response_models import Action
from src.providers.base_provider import BaseProvider
from src.pydantic_models.openai_config import OpenAIConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
	def __init__(self, config: OpenAIConfig):
		self._client = OpenAI(api_key=config.api_key)
		self._model = config.model_id

	def get_action(self, system_prompt: str, history: List[HistoryItem], trailing_prompt: str) -> Action | None:
		messages = []
		messages.append({"role": 'system', "content": system_prompt})

		for turn in history:
			messages.append({"role": 'assistant', "content": turn.model_action})
			messages.append({"role": 'user', "content": turn.action_result})

		messages.append({"role": 'user', "content": trailing_prompt})

		for message in messages:
			logger.debug(f" -- {message['role']}: {message['content']}")

		completion = self._client.beta.chat.completions.parse(
		    model=self._model,
		    messages=messages,
		    response_format=Action,
		)
		return completion.choices[0].message.parsed
