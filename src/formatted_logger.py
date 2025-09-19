from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Any
from colorama import init as colorama_init
from colorama import Fore, Style


class LogLevel(IntEnum):
	DEBUG = 10
	INFO = 20


class BaseLogger(ABC):
	@abstractmethod
	def get_log_level(self) -> int:
		pass

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
	def __init__(self, file_path: str, log_level: int):
		self.file = open(file_path, "w")
		self.log_level = log_level

	def get_log_level(self) -> int:
		return self.log_level

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
	def __init__(self, log_level: int):
		self.log_level = log_level

	def get_log_level(self) -> int:
		return self.log_level

	def code(self, code: str):
		print(Fore.BLUE + code + Style.RESET_ALL)

	def text(self, text: str):
		print(text)

	def header(self, level: int, text: str):
		print(Fore.GREEN + f"{'#' * level} {text}" + Style.RESET_ALL)


class FormattedLogger:
	def __init__(self):
		colorama_init()
		self.loggers: list[BaseLogger] = []

	def register_logger(self, logger: BaseLogger):
		self.loggers.append(logger)

	def code(self, code: Any, log_level: int = LogLevel.INFO):
		for l in self.loggers:
			if log_level >= l.get_log_level():
				l.code(code)

	def text(self, text: Any, log_level: int = LogLevel.INFO):
		for l in self.loggers:
			if log_level >= l.get_log_level():
				l.text(text)

	def header(self, level: int, text: Any, log_level: int = LogLevel.INFO):
		for l in self.loggers:
			if log_level >= l.get_log_level():
				l.header(level, text)


fmtlog = FormattedLogger()
