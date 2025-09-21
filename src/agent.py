from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import queue
import threading
import time
from typing import Any
from src.log_config import logger
from src.formatted_logger import FmtCode, FmtHeader, FmtText, fmtlog
from praw.models import Submission  # type: ignore
from src.commands import AgentEnv, ReplyToContent
from src.pydantic_models.agent_state import HistoryItem, StreamedSubmission
from src.reddit_utils import COMMENT_PREFIX, SubmissionTreeNode, find_content_in_submission_tree, get_author_name, get_comment_tree, get_current_user, list_inbox_comments, show_conversation
from src.utils import confirm_enter, confirm_yes_no, yaml_dump

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
	max_streamed_submissions = 8
	env.state.streamed_submissions = env.state.streamed_submissions[-max_streamed_submissions:]
	env.save_state()


def handle_submissions(env: AgentEnv):
	subreddit = env.reddit.subreddit("+".join(env.agent_config.active_on_subreddits))
	logger.info(f"Monitoring subreddit: {subreddit.display_name}")
	for s in subreddit.stream.submissions():
		if s.author == get_current_user(env.reddit).name:
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


def append_to_history(env: AgentEnv, history_item: HistoryItem):
	env.state.history.append(history_item)
	if len(env.state.history) > env.agent_config.max_history_length:
		env.state.history = env.state.history[-env.agent_config.max_history_length:]


def save_result(env: AgentEnv, history_item: HistoryItem):
	append_to_history(env, history_item)
	env.save_state()


def reply_to_content(env: AgentEnv, content_id: str, reply_text: str, notes_and_strategy: str):
	do_execute = not env.test_mode or confirm_yes_no("Submit the reply?")
	if do_execute:
		command = ReplyToContent(content_id=content_id, reply_text=reply_text)
		action_result = command.execute(env)
		fmtlog([
		    FmtHeader(3, "Action result:"),
		    FmtCode(yaml_dump(action_result)),
		])
		save_result(env, HistoryItem(notes_and_strategy=notes_and_strategy))
	else:
		logger.info("Skipped reply submission on user's request")


def handle_new_post(env: AgentEnv, system_prompt: str, comment_tree: SubmissionTreeNode):
	print("Generating a reply...")
	reply = env.provider.reply_to_post(system_prompt)
	if reply is None:
		fmtlog([FmtText("Error: Could not get reply.")])
		return

	fmtlog([
	    FmtHeader(3, f"Generated reply:"),
	    FmtCode(yaml_dump(reply.model_dump())),
	])

	if not reply.data:
		logger.info("No action taken")
		return

	item_to_reply_to = find_content_in_submission_tree(comment_tree, reply.data.content_id)

	if item_to_reply_to:
		fmtlog([
		    FmtHeader(4, "Item to reply to:"),
		    FmtCode(yaml_dump(item_to_reply_to)),
		])
	else:
		logger.error(f"Error: Could not find content with ID: {reply.data.content_id}")
		return

	reply_to_content(env, reply.data.content_id, reply.data.reply_text, reply.notes_and_strategy)


def handle_inbox_message(env: AgentEnv, system_prompt: str, comment_id: str):
	print("Generating a reply...")
	reply = env.provider.reply_to_inbox(system_prompt)
	if reply is None:
		fmtlog([FmtText("Error: Could not get reply.")])
		return

	fmtlog([
	    FmtHeader(3, f"Generated reply:"),
	    FmtCode(yaml_dump(reply.model_dump())),
	])

	if not reply.data:
		logger.info("No action taken")
		return

	reply_to_content(env, comment_id, reply.data.reply_text, reply.notes_and_strategy)


def get_system_prompt_for_event(env: AgentEnv, event_message: str) -> str:
	event_prompt = [
	    "## Event message:",
	    event_message,
	    "",
	    NOTES_INSTRUCTIONS,
	]

	system_prompt = "\n".join(get_leading_system_prompt(env) + [""] + event_prompt)
	return system_prompt


def handle_new_event(env: AgentEnv):

	fmtlog([FmtText("Waiting for event...")])
	comments = list_inbox_comments(env.reddit)
	fmtlog([FmtText(f"Number of messages in inbox: {len(comments)}")])
	fmtlog([FmtText(f"Number of unread posts: {len(env.state.streamed_submissions)}")])
	stream_submissions_to_state(env)
	if len(comments) > 0:
		comment = comments[0]
		conversation = show_conversation(env.reddit, comment.id)
		json_msg = json.dumps(conversation, ensure_ascii=False, indent=2)

		fmtlog([
		    FmtHeader(3, "New inbox comment event:"),
		    FmtText(f"From: {get_author_name(comment)}"),
		    FmtText(f"Comment: {comment.body}"),
		    FmtText(f"Link: https://reddit.com{comment.context}"),
		])

		event_message = f"You have a new comment in your inbox. Here is the conversation:\n\n```json\n{json_msg}\n```"
		system_prompt = get_system_prompt_for_event(env, event_message)
		handle_inbox_message(env, system_prompt, COMMENT_PREFIX + comment.id)

		if not env.test_mode or confirm_yes_no("Mark comment as read?"):
			comment.mark_read()

	if len(env.state.streamed_submissions) > 0:
		latest_submission = env.reddit.submission(env.state.streamed_submissions[-1].id)
		if not latest_submission.author:
			logger.info(f"Skipping post with unknown author: {latest_submission.id}, {latest_submission.title}")
		else:
			max_comment_tree_size = 20
			comment_tree = get_comment_tree(latest_submission, max_comment_tree_size)
			json_msg = json.dumps(comment_tree.to_dict(), ensure_ascii=False, indent=2)

			fmtlog([
			    FmtHeader(3, "New post event:"),
			    FmtText(f"Subreddit: {latest_submission.subreddit_name_prefixed}"),
			    FmtText(f"Title: {latest_submission.title}"),
			    FmtText(f"URL: {latest_submission.url}"),
			    FmtText(f"Author: {get_author_name(latest_submission)}"),
			    FmtText(f"Text: {latest_submission.selftext}"),
			])

			event_message = f"You have a new post in the monitored subreddits. Here is the conversation tree, with the up to {max_comment_tree_size} highest rated comments:\n\n```json\n{json_msg}\n```"
			system_prompt = get_system_prompt_for_event(env, event_message)
			handle_new_post(env, system_prompt, comment_tree)
		if not env.test_mode or confirm_yes_no("Remove post from stream?"):
			del env.state.streamed_submissions[-1]
	else:
		fmtlog([FmtText("No new events.")])
		return


system_intro = " ".join([
    "You are a Reddit AI agent.",
    "You use a set of commands to interact with Reddit users.",
    "There are commands for replying to comments, creating posts, and more to help you achieve your goals.",
    "For each action you take, you also need to provide a motivation behind the action, which can include any future steps you plan to take.",
    "This will help you keep track of your strategy and make sure you are working towards your goals.",
])


def get_leading_system_prompt(env: AgentEnv) -> list[str]:

	history: list[str] = []
	if len(env.state.history) > 0:
		for i, history_item in enumerate(env.state.history):
			history.append(f"History item {i}: {history_item.notes_and_strategy}")
	else:
		history.append("(No history yet)")

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
	    "## History (your notes on previous actions):",
	    *history,
	    "",
	    "## Current status:",
	    f"Your username is '{get_current_user(env.reddit).name}'.",
	    f"You are active on the following subreddits: {', '.join(env.agent_config.active_on_subreddits)}",
	]


@dataclass
class PerformActionResult:
	notes_and_strategy: str
	action_result: dict[str, Any]


NOTES_INSTRUCTIONS = """You should also provide notes and strategy for the action.
It should include a summary of the event and your response to it. For example, "I replied to a comment about X with Y, with the goal of Z."
This will help you keep track of your strategy and make sure you are working towards your goals."""


def run_agent(env: AgentEnv):
	stream_submissions_thread = threading.Thread(target=handle_submissions, args=(env, ))
	stream_submissions_thread.daemon = True
	stream_submissions_thread.start()
	stream_submissions_to_state(env, wait_once=True)

	while True:

		# Reactions
		try:
			handle_new_event(env)
		except Exception:
			logger.exception()

		if env.test_mode:
			confirm_enter()
		else:
			print("Wait for 10 seconds before handling the next event.")
			time.sleep(10)
