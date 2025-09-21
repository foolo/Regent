from abc import ABC, abstractmethod
from enum import IntEnum
import logging

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class BaseLogger(ABC):
	@abstractmethod
	def log(self, level: int, message: str):
		pass


class LogLevel(IntEnum):
	DEBUG = 10
	INFO = 20
	IMPORTANT = 25
	ERROR = 40


class StdStreamLogger(BaseLogger):
	def __init__(self, log_level: int):
		self.log_level = log_level
		self.logger = logging.Logger('app.StdStreamLogger')
		log_handler = logging.StreamHandler()
		log_handler.setFormatter(logging.Formatter(style='{', fmt='{levelname:8} {message}', datefmt=DATE_FORMAT))
		self.logger.addHandler(log_handler)
		self.logger.setLevel(log_level)

	def log(self, level: int, message: str):
		if level >= self.log_level:
			self.logger.log(level, message)


class FileLogger(BaseLogger):
	def __init__(self, file_path: str, log_level: int):
		self.log_level = log_level
		self.logger = logging.Logger('app.FileLogger')
		log_handler = logging.FileHandler(file_path)
		log_handler.setFormatter(logging.Formatter(style='{', fmt='{levelname:8} {asctime} {message}', datefmt=DATE_FORMAT))
		self.logger.addHandler(log_handler)
		self.logger.setLevel(log_level)

	def log(self, level: int, message: str):
		if level >= self.log_level:
			self.logger.log(level, message)


class AppLogger:
	def __init__(self, log_level: int = 20):
		self.log_level = log_level
		self.loggers: list[BaseLogger] = []

	def register_logger(self, logger: BaseLogger):
		self.loggers.append(logger)

	def debug(self, message: str):
		for logger in self.loggers:
			logger.log(LogLevel.DEBUG, message)

	def info(self, message: str):
		for logger in self.loggers:
			logger.log(LogLevel.INFO, message)

	def error(self, message: str):
		for logger in self.loggers:
			logger.log(LogLevel.ERROR, message)

	def exception(self, e: Exception):
		self.error(f"Exception: {e}")


logger = AppLogger()

formatter = logging.Formatter(
    style='{',
    fmt='{levelname:8} {asctime} {message}',
    datefmt='%Y-%m-%d %H:%M:%S',
)
