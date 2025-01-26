from typing import Any
from openai import OpenAI
from openai.types.chat.parsed_chat_completion import ParsedChatCompletion
from src.providers.base_provider import Action, BaseProvider, Submission
from src.pydantic_models.openai_config import OpenAIConfig
from src.log_config import logger


def log_token_usage(completion: ParsedChatCompletion[Any]):
	usage = completion.usage
	if not usage:
		logger.debug("No token usage information available.")
		return
	logger.debug(f"Token usage: {usage.prompt_tokens} input tokens, {usage.completion_tokens} output tokens")


class OpenAIProvider(BaseProvider):
	def __init__(self, config: OpenAIConfig):
		self.client = OpenAI(api_key=config.api_key)
		self.model = config.model_id

	def get_action(self, system_prompt: str) -> Action | None:
		logger.debug(f"System prompt: {system_prompt}")
		messages: list[Any] = []
		messages.append({"role": 'system', "content": system_prompt})

		completion = self.client.beta.chat.completions.parse(
		    model=self.model,
		    messages=messages,
		    response_format=Action,
		)
		log_token_usage(completion)
		return completion.choices[0].message.parsed

	def generate_submission(self, system_prompt: str) -> Submission | None:
		logger.debug(f"System prompt: {system_prompt}")
		messages: list[Any] = []
		messages.append({"role": 'system', "content": system_prompt})

		completion = self.client.beta.chat.completions.parse(
		    model=self.model,
		    messages=messages,
		    response_format=Submission,
		)
		log_token_usage(completion)
		return completion.choices[0].message.parsed
