from openai import OpenAI
from src.providers.response_models import RedditCommentReply, RedditSubmission
from src.providers.base_provider import BaseProvider
from src.pydantic_models.openai_config import OpenAIConfig


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

	def generate_comment(self, system_prompt: str, prompt: str) -> RedditCommentReply | None:
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
		    response_format=RedditCommentReply,
		)
		return completion.choices[0].message.parsed
