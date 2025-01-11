from typing import Any
from colorama import init as colorama_init
from colorama import Fore, Style


class FormattedLogger:
	def __init__(self):
		colorama_init()

	def code(self, code: Any):
		print(Fore.BLUE + str(code) + Style.RESET_ALL)

	def text(self, text: Any):
		print(str(text))

	def header(self, level: int, text: Any):
		print("")
		print(Fore.GREEN + f"{'#' * level} {str(text)}" + Style.RESET_ALL)
