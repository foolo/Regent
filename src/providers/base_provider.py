from abc import ABC, abstractmethod

from src.providers.response_models import RedditCommentReply, RedditSubmission


class BaseProvider(ABC):
	@abstractmethod
	def generate_submission(self, system_prompt: str, prompt: str) -> RedditSubmission | None:
		pass

	@abstractmethod
	def generate_comment(self, system_prompt: str, prompt: str) -> RedditCommentReply | None:
		pass
