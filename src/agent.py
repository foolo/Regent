from datetime import datetime
import json
import logging
import time
import praw
import praw.models
from src.reddit_utils import get_comment_chain
import praw.models
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_info import AgentInfo

logger = logging.getLogger(__name__)


def get_current_user(reddit: praw.Reddit) -> praw.models.Redditor:
	current_user = reddit.user.me()
	if not current_user:
		raise RuntimeError("No user logged in")
	return current_user


def select_comment(reddit: praw.Reddit, agent_info: AgentInfo) -> praw.models.Comment | None:
	for item in reddit.inbox.unread(limit=None):  # type: ignore
		if isinstance(item, praw.models.Comment):
			current_utc = int(time.time())
			if current_utc - item.created_utc > agent_info.behavior.minimum_comment_age_minutes * 60:
				return item
	return None


def handle_comment(item: praw.models.Comment, reddit: praw.Reddit, agent_info: AgentInfo, provider: BaseProvider, interactive: bool):
	logger.info(f"Handle comment from: {item.author}, Comment: {item.body}")
	root_submission, comments = get_comment_chain(item, reddit)
	conversation_struct = {}
	conversation_struct['root_post'] = {'author': root_submission.author.name, 'title': root_submission.title, 'text': root_submission.selftext}
	conversation_struct['comments'] = [{'author': comment.author.name, 'text': comment.body} for comment in comments]

	system_prompt = agent_info.agent_description + "\n\n"

	system_prompt += "You are in a conversation on Reddit. The conversation is a chain of comments on the subreddit r/" + root_submission.subreddit.display_name + ".\n"
	system_prompt += "Your username in the conversation is " + get_current_user(reddit).name + ".\n"
	system_prompt += "Your task is to first determine whether the last comment in the conversation requires a reply.\n"

	system_prompt += agent_info.behavior.reply_needed_classification + "\n"

	system_prompt += "If a reply is needed, set the 'reply_needed' field to true and provide a reply in the 'body' field. Otherwise set the 'reply_needed' field to false and leave the 'body' field undefined.\n"

	system_prompt += agent_info.behavior.reply_style + "\n"

	prompt = "The conversation is as follows: \n" + json.dumps(conversation_struct, indent=1)
	logger.info("System prompt:")
	logger.info(system_prompt)
	logger.info("Prompt:")
	logger.info(prompt)
	response = provider.generate_comment(system_prompt, prompt)
	if response is None:
		logger.warning("Failed to generate a response")
		return
	logger.info(f"Response:")
	logger.info(response)
	if response.reply_needed:
		if not response.body or response.body == "":
			logger.warning("Reply needed but no body provided")
			return
		if not interactive or input("Post reply? (y/n): ") == "y":
			logger.info("Posting reply...")
			comments[-1].reply(response.body)
			logger.info("Reply posted")
	item.mark_read()


def select_and_handle_comment(reddit: praw.Reddit, agent_info: AgentInfo, provider: BaseProvider, interactive: bool):
	item = select_comment(reddit, agent_info)
	if item:
		handle_comment(item, reddit, agent_info, provider, interactive)
	else:
		logger.info("No comment for handling found")


def create_submission(reddit: praw.Reddit, agent_info: AgentInfo, provider: BaseProvider, interactive: bool):
	prompt = "Generate a reddit submission. " + agent_info.behavior.submission_style
	system_prompt = agent_info.agent_description
	logger.info("System prompt:")
	logger.info(system_prompt)
	logger.info("Prompt:")
	logger.info(prompt)
	response = provider.generate_submission(system_prompt, prompt)
	if response is None:
		logger.error("Failed to generate a response")
		return
	logger.info("Response:")
	logger.info(response)
	if not interactive or input(f"Post submission to {agent_info.active_subreddit}? (y/n): ") == "y":
		logger.info("Posting submission...")
		reddit.subreddit(agent_info.active_subreddit).submit(response.title, selftext=response.selftext)
		logger.info("Submission posted")


def get_latest_submission(current_user: praw.models.Redditor) -> praw.models.Submission | None:
	return next(current_user.submissions.new(limit=1))


def create_submission_if_time(reddit: praw.Reddit, agent_info: AgentInfo, provider: BaseProvider, interactive: bool):
	current_user = get_current_user(reddit)
	latest_submission = get_latest_submission(current_user)
	current_utc = int(time.time())
	if not latest_submission or current_utc > latest_submission.created_utc + agent_info.behavior.minimum_time_between_submissions_hours * 3600:
		create_submission(reddit, agent_info, provider, interactive)
	else:
		logger.info(f"Not enough time has passed since the last submission, which was posted {datetime.fromtimestamp(latest_submission.created_utc)}")


def run_agent(agent_info: AgentInfo, provider: BaseProvider, reddit: praw.Reddit, interactive: bool, iteration_interval: int):
	while True:
		if interactive:
			print('Commands:')
			print("  l=List posts, cs=Create a submission, i=Show inbox, c=Handle comment, d=Default iteration")
			print("Enter command:")
			command = input()
		else:
			command = "d"

		if command == "d":
			select_and_handle_comment(reddit, agent_info, provider, interactive)
			create_submission_if_time(reddit, agent_info, provider, interactive)
		elif command == "c":
			select_and_handle_comment(reddit, agent_info, provider, interactive)
		elif command == "i":
			print("Inbox:")
			for item in reddit.inbox.unread(limit=None):  # type: ignore
				if isinstance(item, praw.models.Comment):
					print(f"Comment from: {item.author}, Comment: {item.body}")
				elif isinstance(item, praw.models.Message):
					print(f"Message from: {item.author}, Subject: {item.subject}, Message: {item.body}")
		elif command == "l":
			print(f'Listing posts from subreddit: {agent_info.active_subreddit}')
			for submission in reddit.subreddit(agent_info.active_subreddit).new(limit=10):
				print(submission.title)
		elif command == "cs":
			create_submission(reddit, agent_info, provider, interactive)
		else:
			print(f"Invalid command: '{command}'")

		if not interactive:
			time.sleep(iteration_interval)
