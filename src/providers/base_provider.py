from abc import ABC, abstractmethod
from typing import List

from src.providers.response_models import Action, RedditReply, RedditSubmission
from src.pydantic_models.agent_state import HistoryItem


class BaseProvider(ABC):
	@abstractmethod
	def generate_submission(self, system_prompt: str, prompt: str) -> RedditSubmission | None:
		pass

	@abstractmethod
	def generate_comment(self, system_prompt: str, prompt: str) -> RedditReply | None:
		pass

	@abstractmethod
	def get_action(self, system_prompt: str, initial_prompt: str, history: List[HistoryItem]) -> Action | None:
		pass
