from abc import ABC, abstractmethod

from pydantic import BaseModel


class Action(BaseModel):
	command: str
	parameters: list[str]
	motivation_behind_the_action: str


class Submission(BaseModel):
	subreddit: str
	title: str
	text: str


class BaseProvider(ABC):
	@abstractmethod
	def get_action(self, system_prompt: str) -> Action | None:
		pass

	@abstractmethod
	def generate_submission(self, system_prompt: str) -> Submission | None:
		pass
