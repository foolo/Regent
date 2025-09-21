from abc import ABC, abstractmethod
from colorama import init as colorama_init
from colorama import Fore, Style

from src.log_config import FileLogger, LogLevel


class MarkupElement(ABC):
	@abstractmethod
	def render_md(self) -> str:
		pass

	@abstractmethod
	def render_terminal(self) -> str:
		pass


class FmtCode(MarkupElement):
	def __init__(self, code: str):
		self.code = code

	def render_md(self) -> str:
		return f"```\n{self.code.strip()}\n```"

	def render_terminal(self) -> str:
		return Fore.LIGHTBLUE_EX + self.code + Style.RESET_ALL


class FmtText(MarkupElement):
	def __init__(self, text: str):
		self.text = text

	def render_md(self) -> str:
		return self.text.strip()

	def render_terminal(self) -> str:
		return Fore.CYAN + self.text + Style.RESET_ALL


class FmtHeader(MarkupElement):
	def __init__(self, level: int, text: str):
		self.level = level
		self.text = text

	def render_md(self) -> str:
		return f"{'#' * self.level} {self.text.strip()}"

	def render_terminal(self) -> str:
		return Fore.GREEN + f"{'#' * self.level} {self.text}" + Style.RESET_ALL


class FormattedLogger:
	def __init__(self, file_logger: FileLogger):
		colorama_init()
		self.file_logger = file_logger

	def log(self, elements: list[MarkupElement]):
		self.file_logger.log(LogLevel.IMPORTANT, "\n\n".join([el.render_md() for el in elements]))
		print("\n".join([el.render_terminal() for el in elements]))


class LogContainer:
	def __init__(self):
		self.formatted_logger = None

	def register_logger(self, fmtlog: FormattedLogger):
		self.formatted_logger = fmtlog


log_container = LogContainer()


def fmtlog(elements: list[MarkupElement]):
	if not log_container.formatted_logger:
		raise ValueError("formatted_logger must be registered in log_container before logging.")
	log_container.formatted_logger.log(elements)
