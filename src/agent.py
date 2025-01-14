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
from praw.models import Comment, Submission  # type: ignore
from src.formatted_logger import FormattedLogger
from src.commands import AgentEnv, Command
from src.pydantic_models.agent_state import AgentState, HistoryItem, StreamedSubmission
from src.reddit_utils import COMMENT_PREFIX, get_author_name, get_current_user
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_config import AgentConfig


def display_json(json_str: str) -> str:
	try:
		obj = json.loads(json_str)
		return yaml.dump(obj, default_flow_style=False)
	except json.JSONDecodeError:
		return json_str


class Agent:
	def __init__(self, state_filename: str, agent_config: AgentConfig, provider: BaseProvider, reddit: Reddit, test_mode: bool, iteration_interval: int):
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
		self.test_mode = test_mode
		self.iteration_interval = iteration_interval
		self.submission_queue: queue.Queue[Submission] = queue.Queue()
		self.fmtlog = FormattedLogger()

	def list_inbox(self) -> list[dict[str, str]]:
		inbox: list[dict[str, str]] = []
		for item in self.reddit.inbox.unread(limit=None):  # type: ignore
			if isinstance(item, Comment):
				inbox.append({
				    'type': 'comment',
				    'content_id': COMMENT_PREFIX + item.id,
				    'author': get_author_name(item),
				    'body': item.body,
				})
		return inbox

	def stream_submissions_to_state(self):
		while True:
			try:
				s = self.submission_queue.get_nowait()
				if s.created_utc <= self.state.streamed_submissions_until_timestamp.timestamp():
					logger.info(f"Skipping post older than {self.state.streamed_submissions_until_timestamp}: {s.title}")
				else:
					self.state.streamed_submissions_until_timestamp = datetime.fromtimestamp(s.created_utc, timezone.utc)
					self.state.streamed_submissions.append(StreamedSubmission(id=s.id, timestamp=datetime.fromtimestamp(s.created_utc, timezone.utc)))
			except queue.Empty:
				break
			submissions_newer_than_max_age: list[StreamedSubmission] = []
			for s in self.state.streamed_submissions:
				if s.timestamp > datetime.now(timezone.utc) - timedelta(hours=self.agent_config.behavior.max_post_age_for_replying_hours):
					submissions_newer_than_max_age.append(s)
				else:
					logger.info(f"Removing post older than {self.agent_config.behavior.max_post_age_for_replying_hours} hours: {s.timestamp}")
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
			max_post_age_for_replying_hours = self.agent_config.behavior.max_post_age_for_replying_hours
			if timestamp < datetime.now(timezone.utc) - timedelta(hours=max_post_age_for_replying_hours):
				logger.debug(f"Skipping post older than {max_post_age_for_replying_hours} hours: {timestamp} {s.id}, {s.title}")
			else:
				logger.debug(f"Queuing new post: {timestamp} {s.id}, {s.title}")
				self.submission_queue.put(s)

	def generate_dashboard(self):
		try:
			unread_messages = len(self.list_inbox())
			return "\n".join([
			    f"Unread messages in inbox: {unread_messages}",
			])
		except Exception as e:
			logger.exception(f"Error generating dashboard: {e}")
			return "Error generating dashboard"

	def save_state(self):
		with open(self.state_filename, 'w') as f:
			f.write(self.state.model_dump_json(indent=2))

	def get_command_list(self) -> list[str]:
		commands: list[str] = []
		for command_name, command_info in Command.registry.items():
			commands.append(f"{command_name} {' '.join(command_info.parameter_names)}  # {command_info.description}")
		return commands

	def run(self):
		stream_submissions_thread = threading.Thread(target=self.handle_submissions)
		stream_submissions_thread.start()

		system_prompt = "\n".join([
		    self.agent_config.agent_description,
		    "",
		    "To acheive your goals, you can interact with Reddit users by replying to comments, creating posts, and more.",
		    "You will be provided with a list of available commands, the recent command history, and a dashboard of the current state (e.g. number of messages in inbox).",
		    "Respond with the command and parameters you want to execute. Also provide a motivation behind the action, and any future steps you plan to take, to help keep track of your strategy.",
		    "You can work in many steps, and the system will remember your previous actions and responses.",
		    "Only use comment IDs you have received from earlier actions. Don't use random comment IDs.",
		    "",
		    "Available commands:",
		] + self.get_command_list())

		self.fmtlog.header(3, "System prompt:")
		self.fmtlog.code(system_prompt)

		self.fmtlog.header(3, "History:")
		if len(self.state.history) == 0:
			self.fmtlog.text("No history yet.")
		for history_item in self.state.history:
			self.fmtlog.header(4, f"Action:")
			self.fmtlog.code(display_json(history_item.model_action))
			self.fmtlog.header(4, "Result:")
			self.fmtlog.code(display_json(history_item.action_result))

		while True:
			dashboard_message = "\n".join([
			    "Dashboard:",
			    self.generate_dashboard(),
			])

			self.fmtlog.header(3, "Dashboard message:")
			self.fmtlog.code(dashboard_message)

			if self.test_mode:
				print("Press enter to continue...", file=sys.stderr)
				input("")

			model_action = self.provider.get_action(system_prompt, self.state.history, dashboard_message)
			if model_action is None:
				self.fmtlog.text("Error: Could not get model action.")
				continue

			self.fmtlog.header(3, f"Model action: {model_action.command}")
			self.fmtlog.code(yaml.dump(model_action.model_dump(), default_flow_style=False))

			if self.test_mode:
				print("Press enter to continue...", file=sys.stderr)
				input("")
			else:
				time.sleep(self.iteration_interval)

			self.stream_submissions_to_state()

			command = Command.decode(model_action)
			action_result = command.execute(AgentEnv(self.reddit, self.state, self.agent_config, self.test_mode))
			self.fmtlog.header(3, "Action result:")
			self.fmtlog.code(yaml.dump(action_result, default_flow_style=False))

			self.state.history.append(
			    HistoryItem(
			        model_action=json.dumps(model_action.model_dump(), ensure_ascii=False),
			        action_result=json.dumps(action_result, ensure_ascii=False),
			    ))

			self.save_state()
