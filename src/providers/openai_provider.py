from openai import OpenAI
from src.providers.base_provider import BaseProvider
from src.pydantic_models.openai_config import OpenAIConfig


class OpenAIProvider(BaseProvider):
	def __init__(self, config: OpenAIConfig):
		self._client = OpenAI(api_key=config.api_key)
		self._model = config.model_id

	def generate_text(self, system_prompt: str, prompt: str) -> str | None:
		completion = self._client.chat.completions.create(model=self._model, messages=[
		    {
		        "role": 'system',
		        "content": system_prompt
		    },
		    {
		        "role": 'user',
		        "content": prompt
		    },
		])
		return completion.choices[0].message.content
