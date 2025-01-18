from typing import Any
from colorama import init as colorama_init
from colorama import Fore, Style
from src.log_config import logger


class FormattedLogger:
	def __init__(self):
		colorama_init()

	def code(self, code: Any):
		print(Fore.BLUE + str(code) + Style.RESET_ALL)
		logger.debug(code)

	def text(self, text: Any):
		print(str(text))
		logger.debug(text)

	def header(self, level: int, text: Any):
		print("")
		header = f"{'#' * level} {str(text)}"
		print(Fore.GREEN + header + Style.RESET_ALL)
		logger.debug(header)


fmtlog = FormattedLogger()
