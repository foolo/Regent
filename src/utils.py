import json
from typing import Any
import yaml
import unittest


def seconds_to_hms(seconds: int) -> str:
	if seconds < 0:
		raise ValueError("seconds must not be negative")
	hours, remainder = divmod(seconds, 3600)
	result: list[str] = []
	if hours:
		result.append(f"{hours}h")
	minutes, seconds = divmod(remainder, 60)
	if minutes and hours < 24:
		result.append(f"{minutes}m")
	if seconds and not hours:
		result.append(f"{seconds}s")
	return ' '.join(result) or "0s"


class TestSecondsToDHMS(unittest.TestCase):
	def test_seconds_to_dhms(self):
		self.assertEqual(seconds_to_hms(0), "0s")
		self.assertEqual(seconds_to_hms(1), "1s")
		self.assertEqual(seconds_to_hms(59), "59s")
		self.assertEqual(seconds_to_hms(60), "1m")
		self.assertEqual(seconds_to_hms(61), "1m 1s")
		self.assertEqual(seconds_to_hms(3600), "1h")
		self.assertEqual(seconds_to_hms(3601), "1h")
		self.assertEqual(seconds_to_hms(3659), "1h")
		self.assertEqual(seconds_to_hms(3660), "1h 1m")
		self.assertEqual(seconds_to_hms(3661), "1h 1m")
		self.assertEqual(seconds_to_hms(82800), "23h")
		self.assertEqual(seconds_to_hms(82801), "23h")
		self.assertEqual(seconds_to_hms(82861), "23h 1m")
		self.assertEqual(seconds_to_hms(86390), "23h 59m")
		self.assertEqual(seconds_to_hms(86400), "24h")
		self.assertEqual(seconds_to_hms(86401), "24h")
		self.assertEqual(seconds_to_hms(86460), "24h")
		self.assertEqual(seconds_to_hms(86461), "24h")
		self.assertEqual(seconds_to_hms(89999), "24h")
		self.assertEqual(seconds_to_hms(90000), "25h")
		self.assertEqual(seconds_to_hms(268200), "74h")


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


if __name__ == '__main__':
	unittest.main()
