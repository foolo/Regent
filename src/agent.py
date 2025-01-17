from datetime import datetime, timedelta, timezone
import json
import os
import queue
import sys
import threading
import time
import yaml
from src.log_config import logger
from praw import Reddit  # type: ignore
from praw.models import Submission  # type: ignore
from src.formatted_logger import FormattedLogger
from src.commands import AgentEnv, Command, CreatePost, ShowConversationWithNewActivity, ShowNewPost
from src.pydantic_models.agent_state import AgentState, HistoryItem, StreamedSubmission
from src.reddit_utils import get_current_user
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_config import AgentConfig


def json_to_yaml(json_str: str) -> str:
	try:
		obj = json.loads(json_str)
		return yaml.dump(obj, default_flow_style=False)
	except json.JSONDecodeError:
		return json_str


class Agent:
	def __init__(self, state_filename: str, agent_config: AgentConfig, provider: BaseProvider, reddit: Reddit, confirm: bool, test_mode: bool, iteration_interval: int):
		if os.path.exists(state_filename):
			with open(state_filename) as f:
				whole_file_as_string = f.read()
				self.state = AgentState.model_validate_json(whole_file_as_string)
		else:
			self.state = AgentState(history=[], streamed_submissions=[], streamed_submissions_until_timestamp=datetime.fromtimestamp(0, timezone.utc))

		self.state_filename = state_filename
		self.agent_config = agent_config
		self.provider = provider
		self.reddit = reddit
		self.confirm = confirm
		self.test_mode = test_mode
		self.iteration_interval = iteration_interval
		self.submission_queue: queue.Queue[Submission] = queue.Queue()
		self.fmtlog = FormattedLogger()

	def stream_submissions_to_state(self, wait_once: bool = False):
		while True:
			try:
				if wait_once:
					s = self.submission_queue.get(timeout=10)
					wait_once = False
				else:
					s = self.submission_queue.get_nowait()
				if s.created_utc <= self.state.streamed_submissions_until_timestamp.timestamp():
					logger.debug(f"Skipping post older than {self.state.streamed_submissions_until_timestamp}: {s.title}")
				else:
					self.state.streamed_submissions_until_timestamp = datetime.fromtimestamp(s.created_utc, timezone.utc)
					self.state.streamed_submissions.append(StreamedSubmission(id=s.id, timestamp=datetime.fromtimestamp(s.created_utc, timezone.utc)))
			except queue.Empty:
				break
			submissions_newer_than_max_age: list[StreamedSubmission] = []
			for s in self.state.streamed_submissions:
				if s.timestamp > datetime.now(timezone.utc) - timedelta(hours=self.agent_config.max_post_age_for_replying_hours):
					submissions_newer_than_max_age.append(s)
				else:
					logger.info(f"Removing post older than {self.agent_config.max_post_age_for_replying_hours} hours: {s.timestamp}")
			self.state.streamed_submissions = submissions_newer_than_max_age
		self.save_state()

	def handle_submissions(self):
		subreddit = self.reddit.subreddit("+".join(self.agent_config.active_on_subreddits))
		logger.info(f"Monitoring subreddit: {subreddit.display_name}")
		for s in subreddit.stream.submissions():
			if s.author == get_current_user(self.reddit):
				logger.debug(f"Skipping own post: {s.id}, {s.title}")
				continue
			if s.selftext == "":
				logger.debug(f"Skipping post without text: {s.id}, {s.title}")
				continue
			timestamp = datetime.fromtimestamp(s.created_utc, timezone.utc)
			max_post_age_for_replying_hours = self.agent_config.max_post_age_for_replying_hours
			if timestamp < datetime.now(timezone.utc) - timedelta(hours=max_post_age_for_replying_hours):
				logger.debug(f"Skipping post older than {max_post_age_for_replying_hours} hours: {timestamp} {s.id}, {s.title}")
			else:
				logger.debug(f"Queuing new post: {timestamp} {s.id}, {s.title}")
				self.submission_queue.put(s)

	def save_state(self):
		with open(self.state_filename, 'w') as f:
			f.write(self.state.model_dump_json(indent=2))

	def get_command_list(self) -> list[str]:
		self.stream_submissions_to_state()
		commands: list[str] = []
		for command_name, command_info in Command.registry.items():
			if command_info.command.available(AgentEnv(self.reddit, self.state, self.agent_config, self.test_mode)):
				commands.append(f"{command_name} {' '.join(command_info.parameter_names)}  # {command_info.description}")
		return commands

	def wait_until_new_command_available(self):
		print("Waiting until new command available...", file=sys.stderr)
		while True:
			time.sleep(self.iteration_interval)
			self.stream_submissions_to_state()
			if ShowNewPost.available(AgentEnv(self.reddit, self.state, self.agent_config, self.test_mode)):
				return
			if ShowConversationWithNewActivity.available(AgentEnv(self.reddit, self.state, self.agent_config, self.test_mode)):
				return
			if CreatePost.available(AgentEnv(self.reddit, self.state, self.agent_config, self.test_mode)):
				return

	def format_history(self) -> str:
		if len(self.state.history) == 0:
			return "(No history yet)"
		history_items: list[str] = []
		for history_item in self.state.history:
			history_items.append("### Your action:")
			history_items.append(f"```yaml\n{json_to_yaml(history_item.model_action)}\n```")
			history_items.append("")
			history_items.append("### Result:")
			history_items.append(f"```yaml\n{json_to_yaml(history_item.action_result)}\n```")
		return "\n".join(history_items)

	def append_to_history(self, history_item: HistoryItem):
		self.state.history.append(history_item)
		if len(self.state.history) > self.agent_config.max_history_length:
			self.state.history = self.state.history[-self.agent_config.max_history_length:]

	def run(self):
		stream_submissions_thread = threading.Thread(target=self.handle_submissions)
		stream_submissions_thread.daemon = True
		stream_submissions_thread.start()
		self.stream_submissions_to_state(wait_once=True)

		system_message = f"You are a Reddit AI agent. You use a set of commands to interact with Reddit users. There are commands for replying to comments, creating posts, and more to help you achieve your goals. For each action you take, you also need to provide a motivation behind the action, which can include any future steps you plan to take. This will help you keep track of your strategy and make sure you are working towards your goals. You will be provided with a history of your recent actions (up to {self.agent_config.max_history_length} actions), your motivations, and the responses of the actions. You will also be provided with a list of available commands to perform your actions."

		self.fmtlog.header(3, "History:")
		if len(self.state.history) == 0:
			self.fmtlog.text("No history yet.")
		for history_item in self.state.history:
			self.fmtlog.header(4, f"Action:")
			self.fmtlog.code(json_to_yaml(history_item.model_action))
			self.fmtlog.header(4, "Result:")
			self.fmtlog.code(json_to_yaml(history_item.action_result))

		while True:
			system_prompt = "\n".join([
			    system_message,
			    "",
			    "## Agent description:",
			    self.agent_config.agent_description,
			    "",
			    "## History:",
			    "",
			    self.format_history(),
			])

			user_prompt = "\n".join([
			    f"Your username is '{get_current_user(self.reddit).name}'.",
			    "",
			    "## Available commands:",
			] + self.get_command_list() + [
			    "",
			    "Respond with the command and parameters you want to execute. Also provide a motivation behind the action, and any future steps you plan to take, to help keep track of your strategy."
			])

			self.fmtlog.header(3, "User prompt:")
			self.fmtlog.code(user_prompt)

			model_action = self.provider.get_action(system_prompt, user_prompt)
			if model_action is None:
				self.fmtlog.text("Error: Could not get model action.")
				continue

			self.fmtlog.header(3, f"Model action: {model_action.command}")
			self.fmtlog.code(yaml.dump(model_action.model_dump(), default_flow_style=False))

			if self.confirm:
				print("Press enter to continue...", file=sys.stderr)
				input("")

			self.stream_submissions_to_state()

			command = Command.decode(model_action)
			action_result = command.execute(AgentEnv(self.reddit, self.state, self.agent_config, self.test_mode))
			self.fmtlog.header(3, "Action result:")
			self.fmtlog.code(yaml.dump(action_result, default_flow_style=False))

			self.append_to_history(
			    HistoryItem(
			        model_action=json.dumps(model_action.model_dump(), ensure_ascii=False),
			        action_result=json.dumps(action_result, ensure_ascii=False),
			    ))

			self.save_state()

			if self.confirm:
				print("Press enter to continue...", file=sys.stderr)
				input("")
			else:
				self.wait_until_new_command_available()
