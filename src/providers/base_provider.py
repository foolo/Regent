from abc import ABC, abstractmethod

class BaseProvider(ABC):
	@abstractmethod
	def generate_text(self, system_prompt: str, prompt: str) -> str | None:
		pass
