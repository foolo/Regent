from abc import ABC, abstractmethod

from src.reddit_submission import RedditSubmission


class BaseProvider(ABC):
	@abstractmethod
	def generate_submission(self, system_prompt: str, prompt: str) -> RedditSubmission | None:
		pass

	@abstractmethod
	def generate_comment(self, system_prompt: str, prompt: str) -> str | None:
		pass
