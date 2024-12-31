from abc import ABC, abstractmethod

from src.reddit_submission import RedditSubmission


class BaseProvider(ABC):
	@abstractmethod
	def generate_submission(self, system_prompt: str, prompt: str) -> RedditSubmission | None:
		pass
