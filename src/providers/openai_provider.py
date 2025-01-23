from typing import Any
from openai import OpenAI
from src.providers.base_provider import Action, BaseProvider, Submission
from src.pydantic_models.openai_config import OpenAIConfig


class OpenAIProvider(BaseProvider):
	def __init__(self, config: OpenAIConfig):
		self.client = OpenAI(api_key=config.api_key)
		self.model = config.model_id

	def get_action(self, system_prompt: str) -> Action | None:
		messages: list[Any] = []
		messages.append({"role": 'system', "content": system_prompt})

		completion = self.client.beta.chat.completions.parse(
		    model=self.model,
		    messages=messages,
		    response_format=Action,
		)
		return completion.choices[0].message.parsed

	def generate_submission(self, system_prompt: str) -> Submission | None:
		messages: list[Any] = []
		messages.append({"role": 'system', "content": system_prompt})

		completion = self.client.beta.chat.completions.parse(
		    model=self.model,
		    messages=messages,
		    response_format=Submission,
		)
		return completion.choices[0].message.parsed
