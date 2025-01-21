from datetime import datetime, timedelta, timezone
import json
import queue
import threading
import time
from src.log_config import logger
from src.formatted_logger import fmtlog
from praw.models import Submission  # type: ignore
from src.commands import AgentEnv, Command, CreatePost, ShowConversationWithNewActivity, ShowNewPost
from src.pydantic_models.agent_state import HistoryItem, StreamedSubmission
from src.reddit_utils import get_current_user, list_inbox_comments
from src.utils import confirm_yes_no, json_to_yaml, yaml_dump

submission_queue: queue.Queue[Submission] = queue.Queue()


def stream_submissions_to_state(env: AgentEnv, wait_once: bool = False):
	while True:
		try:
			if wait_once:
				s = submission_queue.get(timeout=10)
				wait_once = False
			else:
				s = submission_queue.get_nowait()
			if s.created_utc <= env.state.streamed_submissions_until_timestamp.timestamp():
				logger.debug(f"Skipping post older than {env.state.streamed_submissions_until_timestamp}: {s.title}")
			else:
				env.state.streamed_submissions_until_timestamp = datetime.fromtimestamp(s.created_utc, timezone.utc)
				env.state.streamed_submissions.append(StreamedSubmission(id=s.id, timestamp=datetime.fromtimestamp(s.created_utc, timezone.utc)))
		except queue.Empty:
			break
		submissions_newer_than_max_age: list[StreamedSubmission] = []
		for s in env.state.streamed_submissions:
			if s.timestamp > datetime.now(timezone.utc) - timedelta(hours=env.agent_config.max_post_age_for_replying_hours):
				submissions_newer_than_max_age.append(s)
			else:
				logger.info(f"Removing post older than {env.agent_config.max_post_age_for_replying_hours} hours: {s.timestamp}")
		env.state.streamed_submissions = submissions_newer_than_max_age
	env.save_state()


def handle_submissions(env: AgentEnv):
	subreddit = env.reddit.subreddit("+".join(env.agent_config.active_on_subreddits))
	logger.info(f"Monitoring subreddit: {subreddit.display_name}")
	for s in subreddit.stream.submissions():
		if s.author == get_current_user(env.reddit):
			logger.debug(f"Skipping own post: {s.id}, {s.title}")
			continue
		if not s.is_self:
			logger.debug(f"Skipping post without text: {s.id}, {s.title}")
			continue
		timestamp = datetime.fromtimestamp(s.created_utc, timezone.utc)
		max_post_age_for_replying_hours = env.agent_config.max_post_age_for_replying_hours
		if timestamp < datetime.now(timezone.utc) - timedelta(hours=max_post_age_for_replying_hours):
			logger.debug(f"Skipping post older than {max_post_age_for_replying_hours} hours: {timestamp} {s.id}, {s.title}")
		else:
			logger.debug(f"Queuing new post: {timestamp} {s.id}, {s.title}")
			submission_queue.put(s)


def get_command_list(env: AgentEnv) -> list[str]:
	stream_submissions_to_state(env)
	commands: list[str] = []
	for command_name, command_info in Command.registry.items():
		if command_info.command.available(env):
			commands.append(f"{command_name} {' '.join(command_info.parameter_names)}  # {command_info.description}")
	return commands


def wait_until_new_command_available(env: AgentEnv):
	print("Waiting until new command available...")
	while True:
		time.sleep(10)
		stream_submissions_to_state(env)
		if ShowNewPost.available(env):
			return
		if ShowConversationWithNewActivity.available(env):
			return
		if CreatePost.available(env):
			return


def format_history(env: AgentEnv) -> str:
	if len(env.state.history) == 0:
		return "(No history yet)"
	history_items: list[str] = []
	for i, history_item in enumerate(env.state.history):
		history_items.append(f"### Your action (history item {i + 1}):")
		history_items.append(f"```json\n{history_item.model_action}\n```")
		history_items.append("")
		history_items.append(f"### Result of the action:")
		history_items.append(f"```json\n{history_item.action_result}\n```")
	return "\n".join(history_items)


def append_to_history(env: AgentEnv, history_item: HistoryItem):
	env.state.history.append(history_item)
	if len(env.state.history) > env.agent_config.max_history_length:
		env.state.history = env.state.history[-env.agent_config.max_history_length:]


def run_agent(env: AgentEnv):
	stream_submissions_thread = threading.Thread(target=handle_submissions, args=(env, ))
	stream_submissions_thread.daemon = True
	stream_submissions_thread.start()
	stream_submissions_to_state(env, wait_once=True)

	system_intro = f"You are a Reddit AI agent. You use a set of commands to interact with Reddit users. There are commands for replying to comments, creating posts, and more to help you achieve your goals. For each action you take, you also need to provide a motivation behind the action, which can include any future steps you plan to take. This will help you keep track of your strategy and make sure you are working towards your goals. You will be provided with a history of your recent actions (up to {env.agent_config.max_history_length} actions), your motivations, and the responses of the actions. You will also be provided with a list of available commands to perform your actions. Before you decide on an action, you should take the last action of the history into account, to follow up on the motivation you provided for the last action."

	fmtlog.header(3, "System message:")
	fmtlog.text(system_intro)
	fmtlog.header(3, "Agent description:")
	fmtlog.text(env.agent_config.agent_description)

	fmtlog.header(3, "History:")
	if len(env.state.history) == 0:
		fmtlog.text("No history yet.")
	for history_item in env.state.history:
		fmtlog.header(4, f"Action:")
		fmtlog.code(json_to_yaml(history_item.model_action))
		fmtlog.header(4, "Result:")
		fmtlog.code(json_to_yaml(history_item.action_result))

	while True:
		status_message = [
		    f"Number of messages in inbox: {len(list_inbox_comments(env.reddit))}",
		    f"Number of unread posts: {len(env.state.streamed_submissions)}",
		    f"Your username is '{get_current_user(env.reddit).name}'.",
		]
		fmtlog.header(3, "Status message:")
		fmtlog.text("\n".join(status_message))

		system_prompt = "\n".join([
		    system_intro,
		    "",
		    "## Agent description:",
		    env.agent_config.agent_description,
		    "",
		    "## Current status:",
		] + status_message + [
		    "",
		    "## Available commands:",
		] + get_command_list(env) + [
		    "",
		    "## History:",
		    "",
		    format_history(env),
		    "(End of history)",
		    "",
		    "Now, respond with the command you want to execute.",
		])

		model_action = env.provider.get_action(system_prompt)
		if model_action is None:
			fmtlog.text("Error: Could not get model action.")
			continue

		fmtlog.header(3, f"Model action: {model_action.command}")
		fmtlog.code(yaml_dump(model_action.model_dump()))

		do_execute = not env.test_mode or confirm_yes_no("Execute the action?")

		stream_submissions_to_state(env)
		if do_execute:
			command = Command.decode(model_action)
			action_result = command.execute(env)
		else:
			action_result = {"note": "Skipped execution"}
		fmtlog.header(3, "Action result:")
		fmtlog.code(yaml_dump(action_result))

		append_to_history(env, HistoryItem(
		    model_action=json.dumps(model_action.model_dump(), ensure_ascii=False),
		    action_result=json.dumps(action_result, ensure_ascii=False),
		))

		env.save_state()

		if env.test_mode:
			input("Press enter to continue...")
		else:
			wait_until_new_command_available(env)
