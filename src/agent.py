from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import queue
import threading
import time
from typing import Any
from src.log_config import logger
from src.formatted_logger import fmtlog
from praw.models import Submission  # type: ignore
from src.commands import AgentEnv, Command, CommandDecodeError, CreatePost, time_until_create_post_possible
from src.pydantic_models.agent_state import HistoryItem, StreamedSubmission
from src.reddit_utils import get_comment_tree, get_current_user, list_inbox_comments, show_conversation
from src.utils import confirm_yes_no, json_to_yaml, yaml_dump

submission_queue: queue.Queue[Submission] = queue.Queue()


def already_streamed(env: AgentEnv, submission: Submission) -> bool:
	for s in env.state.streamed_submissions:
		if s.id == submission.id:
			return True
	return False


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
				if already_streamed(env, s):
					logger.info(f"Skipping already streamed post: {s.id}, {s.title}")
				else:
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


def append_to_history(env: AgentEnv, history_item: HistoryItem):
	env.state.history.append(history_item)
	if len(env.state.history) > env.agent_config.max_history_length:
		env.state.history = env.state.history[-env.agent_config.max_history_length:]


def get_new_event(env: AgentEnv) -> str | None:
	fmtlog.header(3, "Waiting for event...")
	fmtlog.text(f"Number of messages in inbox: {len(list_inbox_comments(env.reddit))}")
	fmtlog.text(f"Number of unread posts: {len(env.state.streamed_submissions)}")
	stream_submissions_to_state(env)
	comments = list_inbox_comments(env.reddit)
	if len(comments) > 0:
		comment = comments[0]
		mark_as_read = not env.test_mode or confirm_yes_no("Mark comment as read?")
		if mark_as_read:
			comment.mark_read()
		conversation = show_conversation(env.reddit, comment.id)
		json_msg = json.dumps(conversation, ensure_ascii=False, indent=2)
		return f"You have a new comment in your inbox. Here is the conversation:\n\n```json\n{json_msg}\n```"
	if len(env.state.streamed_submissions) > 0:
		latest_submission = env.reddit.submission(env.state.streamed_submissions[-1].id)
		del env.state.streamed_submissions[-1]
		max_comment_tree_size = 20
		comment_tree = get_comment_tree(env.reddit, latest_submission, max_comment_tree_size)
		json_msg = json.dumps(comment_tree, ensure_ascii=False, indent=2)
		return f"You have a new post in the monitored subreddits. Here is the conversation tree, with the {max_comment_tree_size} highest rated comments:\n\n```json\n{json_msg}\n```"
	if CreatePost.available(env):
		return "You can choose to create a new post."
	return None


system_intro = " ".join([
    "You are a Reddit AI agent.",
    "You use a set of commands to interact with Reddit users.",
    "There are commands for replying to comments, creating posts, and more to help you achieve your goals.",
    "For each action you take, you also need to provide a motivation behind the action, which can include any future steps you plan to take.",
    "This will help you keep track of your strategy and make sure you are working towards your goals.",
])


def get_leading_system_prompt(env: AgentEnv) -> list[str]:
	return [
	    system_intro,
	    "",
	    f"You will be provided with:",
	    "An event message that describes the last incoming event, which you can react to.",
	    "A list of available commands to perform your actions.",
	    "",
	    "## Agent instructions:",
	    env.agent_config.agent_instructions,
	    "",
	    "## Current status:",
	    f"Your username is '{get_current_user(env.reddit).name}'.",
	    f"You are active on the following subreddits: {', '.join(env.agent_config.active_on_subreddits)}",
	]


def save_result(env: AgentEnv, model_action: dict[str, Any], action_result: dict[str, Any]):
	fmtlog.header(3, "Action result:")
	fmtlog.code(yaml_dump(action_result))

	append_to_history(env, HistoryItem(
	    model_action=json.dumps(model_action, ensure_ascii=False),
	    action_result=json.dumps(action_result, ensure_ascii=False),
	))

	env.save_state()


@dataclass
class PerformActionResult:
	model_action: dict[str, Any]
	action_result: dict[str, Any]


def perform_action(env: AgentEnv) -> PerformActionResult | None:
	if env.agent_config.can_create_posts and time_until_create_post_possible(env.reddit, env.agent_config) <= 0:
		system_prompt = "\n".join(get_leading_system_prompt(env) + [
		    "",
		    "Your task is to create a new post in one of the subreddits you are active on.",
		])
		fmtlog.header(3, "System prompt:")
		fmtlog.text(system_prompt)
		submission = env.provider.generate_submission(system_prompt)
		if submission is None:
			fmtlog.text("Error: Could not get model action.")
			return None
		fmtlog.header(3, "Model generated submission")
		fmtlog.code(yaml_dump(submission.model_dump()))
		do_execute = not env.test_mode or confirm_yes_no("Execute the action?")
		if do_execute:
			subreddit = submission.subreddit.lower().strip()
			if subreddit.startswith("r/"):
				subreddit = subreddit[2:]
			if not subreddit in [subreddit.lower() for subreddit in env.agent_config.active_on_subreddits]:
				return PerformActionResult(model_action=submission.model_dump(), action_result={'error': f"You are not active on the subreddit: {subreddit}"})
			env.reddit.subreddit(subreddit).submit(submission.title, selftext=submission.text)
			return PerformActionResult(model_action=submission.model_dump(), action_result={'result': 'Post created'})
		else:
			return PerformActionResult(model_action=submission.model_dump(), action_result={'note': 'Skipped execution'})


def handle_event(env: AgentEnv, event_message: str):
	system_prompt = "\n".join(
	    get_leading_system_prompt(env) + [
	        "",
	        "## Event message:",
	        event_message,
	        "",
	        "## Available commands:",
	    ] + get_command_list(env) + [
	        "",
	        "Now, respond with the command you want to execute.",
	    ])

	fmtlog.header(3, "System prompt:")
	fmtlog.text(system_prompt)

	model_action = env.provider.get_action(system_prompt)
	if model_action is None:
		fmtlog.text("Error: Could not get model action.")
		return

	fmtlog.header(3, f"Model action: {model_action.command}")
	fmtlog.code(yaml_dump(model_action.model_dump()))

	do_execute = not env.test_mode or confirm_yes_no("Execute the action?")

	stream_submissions_to_state(env)
	if do_execute:
		try:
			command = Command.decode(model_action)
			action_result = command.execute(env)
		except CommandDecodeError as e:
			action_result = {"error": f"Could not decode command: {e}"}
	else:
		action_result = {"note": "Skipped execution"}

	save_result(env, model_action.model_dump(), action_result)


def run_agent(env: AgentEnv):
	stream_submissions_thread = threading.Thread(target=handle_submissions, args=(env, ))
	stream_submissions_thread.daemon = True
	stream_submissions_thread.start()
	stream_submissions_to_state(env, wait_once=True)

	fmtlog.header(3, "History:")
	if len(env.state.history) == 0:
		fmtlog.text("No history yet.")
	for history_item in env.state.history:
		fmtlog.header(4, f"Action:")
		fmtlog.code(json_to_yaml(history_item.model_action))
		fmtlog.header(4, "Result:")
		fmtlog.code(json_to_yaml(history_item.action_result))

	while True:

		# Reactions
		try:
			event_message = get_new_event(env)
			if event_message:
				handle_event(env, event_message)
			else:
				fmtlog.text("No new events.")
		except Exception:
			logger.exception("Error in wait_for_event")

		if env.test_mode:
			input("Press enter to continue...")
		else:
			print("Wait for 10 seconds before handling the next event.")
			time.sleep(10)

		# Actions
		try:
			perform_action_result = perform_action(env)
			if perform_action_result:
				save_result(env, perform_action_result.model_action, perform_action_result.action_result)
			else:
				fmtlog.text("No action performed.")
		except Exception:
			logger.exception("Error in perform_action")

		if env.test_mode:
			input("Press enter to continue...")
		else:
			print("Wait for 10 seconds before handling the next event.")
			time.sleep(10)
