from abc import ABC, abstractmethod

from pydantic import BaseModel


class Action(BaseModel):
	command: str
	parameters: list[str]
	motivation_behind_the_action: str


class BaseProvider(ABC):
	@abstractmethod
	def get_action(self, system_prompt: str, trailing_prompt: str) -> Action | None:
		pass
