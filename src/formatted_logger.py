from abc import ABC, abstractmethod
from colorama import init as colorama_init
from colorama import Fore, Style

from src.log_config import FileLogger, LogLevel


class BaseLogger(ABC):
	@abstractmethod
	def code(self, code: str):
		pass

	@abstractmethod
	def text(self, text: str):
		pass

	@abstractmethod
	def header(self, level: int, text: str):
		pass


class MarkdownLogger(BaseLogger):
	def __init__(self, logger: FileLogger):
		self.logger = logger

	def code(self, code: str):
		self.logger.log(LogLevel.IMPORTANT, f"```\n{code.strip()}\n```\n\n")

	def text(self, text: str):
		self.logger.log(LogLevel.IMPORTANT, text.strip())

	def header(self, level: int, text: str):
		self.logger.log(LogLevel.IMPORTANT, f"{'#' * level} {text.strip()}")


class ColoredTerminalLogger(BaseLogger):
	def __init__(self, log_level: int):
		self.log_level = log_level

	def get_log_level(self) -> int:
		return self.log_level

	def code(self, code: str):
		print(Fore.LIGHTBLUE_EX + code + Style.RESET_ALL)

	def text(self, text: str):
		print(Fore.CYAN + text + Style.RESET_ALL)

	def header(self, level: int, text: str):
		print(Fore.GREEN + f"{'#' * level} {text}" + Style.RESET_ALL)


class FormattedLogger:
	def __init__(self):
		colorama_init()
		self.loggers: list[BaseLogger] = []

	def register_logger(self, logger: BaseLogger):
		self.loggers.append(logger)

	def code(self, code: str):
		for l in self.loggers:
			l.code(code)

	def text(self, text: str):
		for l in self.loggers:
			l.text(text)

	def header(self, level: int, text: str):
		for l in self.loggers:
			l.header(level, text)


fmtlog = FormattedLogger()
