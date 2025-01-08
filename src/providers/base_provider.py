from abc import ABC, abstractmethod

from src.history import History
from src.providers.response_models import ActionDecision, RedditReply, RedditSubmission


class BaseProvider(ABC):
	@abstractmethod
	def generate_submission(self, system_prompt: str, prompt: str) -> RedditSubmission | None:
		pass

	@abstractmethod
	def generate_comment(self, system_prompt: str, prompt: str) -> RedditReply | None:
		pass

	@abstractmethod
	def get_action(self, system_prompt: str, history: History, prompt: str) -> ActionDecision | None:
		pass
