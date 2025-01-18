from abc import ABC, abstractmethod
from typing import Any
from colorama import init as colorama_init
from colorama import Fore, Style
from src.log_config import logger


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
	def __init__(self, file_path: str):
		self.file = open(file_path, "w")

	def code(self, code: str):
		self.file.write(f"```\n{code.strip()}\n```\n\n")
		self.file.flush()

	def text(self, text: str):
		self.file.write(text.strip() + "\n\n")
		self.file.flush()

	def header(self, level: int, text: str):
		self.file.write(f"{'#' * level} {text.strip()}\n\n")
		self.file.flush()


class ColoredTerminalLogger(BaseLogger):
	def code(self, code: str):
		print(Fore.BLUE + code + Style.RESET_ALL)

	def text(self, text: str):
		print(text)

	def header(self, level: int, text: str):
		print(Fore.GREEN + f"{'#' * level} {text}" + Style.RESET_ALL)


class DebugLogger(BaseLogger):
	def code(self, code: str):
		logger.debug(code)

	def text(self, text: str):
		logger.debug(text)

	def header(self, level: int, text: str):
		logger.debug(f"{'#' * level} {text}")


class FormattedLogger:
	def __init__(self):
		colorama_init()
		self.loggers: list[BaseLogger] = []

	def register_logger(self, logger: BaseLogger):
		self.loggers.append(logger)

	def code(self, code: Any):
		for l in self.loggers:
			l.code(code)

	def text(self, text: Any):
		for l in self.loggers:
			l.text(text)

	def header(self, level: int, text: Any):
		for l in self.loggers:
			l.header(level, text)


fmtlog = FormattedLogger()
