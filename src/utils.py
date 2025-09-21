import json
from typing import Any
import yaml
import unittest


def yaml_dump(obj: Any) -> str:
	return yaml.dump(obj, default_flow_style=False, allow_unicode=True, sort_keys=False)


def json_to_yaml(json_str: str) -> str:
	try:
		obj = json.loads(json_str)
		return yaml_dump(obj)
	except json.JSONDecodeError:
		return json_str


def confirm_yes_no(prompt: str) -> bool:
	while True:
		response = input(f"{prompt} (y/n) ").strip().lower()
		if response == 'y':
			return True
		elif response == 'n':
			return False
		else:
			print("Please enter 'y' or 'n'.")


def confirm_enter():
	input("Press enter to continue...")


if __name__ == '__main__':
	unittest.main()
