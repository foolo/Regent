from abc import ABC, abstractmethod

from src.providers.response_models import Action
from src.pydantic_models.agent_state import HistoryItem


class BaseProvider(ABC):
	@abstractmethod
	def get_action(self, system_prompt: str, history: list[HistoryItem], trailing_prompt: str) -> Action | None:
		pass
