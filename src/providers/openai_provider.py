from typing import Any
from openai import OpenAI
from openai.types.chat.parsed_chat_completion import ParsedChatCompletion
from src.providers.base_provider import BaseProvider, PostReply, InboxReply
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

	def reply_to_post(self, system_prompt: str) -> PostReply | None:
		logger.debug(f"System prompt: {system_prompt}")
		messages: list[Any] = []
		messages.append({"role": 'developer', "content": system_prompt})
		command_specific_message = "Respond with the content_id (the reddit comment ID) you want to reply to and the reply text. If you decide not to reply, let the data field be None."
		messages.append({"role": 'developer', "content": command_specific_message})

		completion = self.client.beta.chat.completions.parse(
		    model=self.model,
		    messages=messages,
		    response_format=PostReply,
		)
		log_token_usage(completion)
		return completion.choices[0].message.parsed

	def reply_to_inbox(self, system_prompt: str) -> InboxReply | None:
		logger.debug(f"System prompt: {system_prompt}")
		messages: list[Any] = []
		messages.append({"role": 'system', "content": system_prompt})

		completion = self.client.beta.chat.completions.parse(
		    model=self.model,
		    messages=messages,
		    response_format=InboxReply,
		)
		log_token_usage(completion)
		return completion.choices[0].message.parsed
