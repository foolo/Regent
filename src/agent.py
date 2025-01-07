from datetime import datetime
import json
import logging
import queue
import random
import threading
import time
import praw
import praw.models
from src.reddit_utils import get_comment_chain
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_info import ActiveOnSubreddit, AgentInfo

logger = logging.getLogger(__name__)


def get_current_user(reddit: praw.Reddit) -> praw.models.Redditor:
	current_user = reddit.user.me()
	if not current_user:
		raise RuntimeError("No user logged in")
	return current_user


def select_comment(reddit: praw.Reddit, agent_info: AgentInfo) -> praw.models.Comment | None:
	for item in reddit.inbox.unread(limit=None):  # type: ignore
		if isinstance(item, praw.models.Comment):
			if not item.author:
				logger.info("Skipping comment from deleted user")
				continue
			if item.author == get_current_user(reddit):
				logger.info("Skipping own comment")
				continue
			current_utc = int(time.time())
			if current_utc - item.created_utc > agent_info.behavior.reply_delay * 60:
				return item
	return None


def get_author_name(item: praw.models.Comment | praw.models.Submission) -> str:
	if not item.author:
		return "[unknown/deleted]"
	return item.author.name


def handle_comment(item: praw.models.Comment, reddit: praw.Reddit, agent_info: AgentInfo, provider: BaseProvider, interactive: bool):
	logger.info(f"Handle comment from: {item.author}, Comment: {item.body}")
	root_submission, comments = get_comment_chain(item, reddit)
	conversation_struct = {}
	conversation_struct['root_post'] = {'author': get_author_name(root_submission), 'title': root_submission.title, 'text': root_submission.selftext}
	conversation_struct['comments'] = [{'author': get_author_name(comment), 'text': comment.body} for comment in comments]
	system_prompt = [
	    agent_info.agent_description + "\n",
	    f"You are in a conversation on Reddit. The conversation is a chain of comments on the subreddit r/{root_submission.subreddit.display_name}",
	    f"Your username in the conversation is {get_current_user(reddit).name}.",
	    f"Your task is to first determine whether the last comment in the conversation requires a reply.",
	    agent_info.behavior.comment_reply_needed_classification,
	    "If a reply is needed, set the 'reply_needed' field to true and provide a reply in the 'body' field. Otherwise set the 'reply_needed' field to false and leave the 'body' field undefined.",
	    agent_info.behavior.reply_style,
	]

	prompt = [
	    "The conversation is as follows:",
	    json.dumps(conversation_struct, indent=1),
	]
	logger.info("System prompt:")
	logger.info(system_prompt)
	logger.info("Prompt:")
	logger.info(prompt)
	response = provider.generate_comment("\n".join(system_prompt), "\n".join(prompt))
	if response is None:
		logger.error("Failed to generate a response")
		return
	logger.info(f"Response:")
	logger.info(response)
	if response.reply_needed:
		if not response.body or response.body == "":
			logger.error("Reply needed but no body provided")
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


def select_subreddit(agent_info: AgentInfo) -> ActiveOnSubreddit:
	return random.choice(agent_info.active_on_subreddits)


def create_submission(reddit: praw.Reddit, agent_info: AgentInfo, provider: BaseProvider, interactive: bool):
	subreddit = select_subreddit(agent_info)
	prompt = [f"Generate a reddit post for the r/{subreddit.name} subreddit. " + agent_info.behavior.post_style]
	if subreddit.post_instructions:
		prompt.append(subreddit.post_instructions)
	system_prompt = agent_info.agent_description
	logger.info("System prompt:")
	logger.info(system_prompt)
	logger.info("Prompt:")
	logger.info(prompt)
	response = provider.generate_submission(system_prompt, "\n".join(prompt))
	if response is None:
		logger.error("Failed to generate a response")
		return
	logger.info("Response:")
	logger.info(response)
	if not interactive or input(f"Publish post to {subreddit}? (y/n): ") == "y":
		logger.info("Publishing post...")
		reddit.subreddit(subreddit.name).submit(response.title, selftext=response.selftext)
		logger.info("Post published")


def get_latest_submission(current_user: praw.models.Redditor) -> praw.models.Submission | None:
	return next(current_user.submissions.new(limit=1))


def create_submission_if_time(reddit: praw.Reddit, agent_info: AgentInfo, provider: BaseProvider, interactive: bool):
	current_user = get_current_user(reddit)
	latest_submission = get_latest_submission(current_user)
	current_utc = int(time.time())
	if not latest_submission or current_utc > latest_submission.created_utc + agent_info.behavior.minimum_time_between_posts_hours * 3600:
		create_submission(reddit, agent_info, provider, interactive)
	else:
		logger.info(f"Not enough time has passed since the last post, which was published {datetime.fromtimestamp(latest_submission.created_utc)}")


def handle_submissions(reddit: praw.Reddit, subreddits: list[str], agent_info: AgentInfo, provider: BaseProvider):
	def handle_submission(s: praw.models.Submission):
		logger.info(f"Handle post from: {s.author}, Title: {s.title}, Text: {s.selftext}")
		system_prompt = [
		    agent_info.agent_description + "\n",
		    f"You are looking at a post on Reddit, in the subreddit r/{s.subreddit.display_name}",
		    f"Your task is to first determine whether the post requires a reply.",
		    agent_info.behavior.post_reply_needed_classification,
		    "If a reply is needed, set the 'reply_needed' field to true and provide a reply in the 'body' field. Otherwise set the 'reply_needed' field to false and leave the 'body' field undefined.",
		    agent_info.behavior.reply_style,
		]

		prompt = [
		    "The post is as follows:",
		    json.dumps({
		        'author': get_author_name(s.author.name),
		        'title': s.title,
		        'text': s.selftext
		    }, indent=1),
		]
		logger.info("System prompt:")
		logger.info(system_prompt)
		logger.info("Prompt:")
		logger.info(prompt)
		response = provider.generate_comment("\n".join(system_prompt), "\n".join(prompt))
		if response is None:
			logger.error("Failed to generate a response")
			return
		logger.info(f"Response:")
		logger.info(response)
		if response.reply_needed:
			if not response.body or response.body == "":
				logger.error("Reply needed but no body provided")
				return
			delay_seconds = agent_info.behavior.reply_delay * 60
			logger.info(f"Posting reply in {delay_seconds} seconds...")
			time.sleep(delay_seconds)
			s.reply(response.body)
			logger.info("Reply posted")

	subreddit = reddit.subreddit("+".join(subreddits))
	print(f"Monitoring subreddit: {subreddit.display_name}")
	for s in subreddit.stream.submissions(skip_existing=True):
		if s.author == get_current_user(reddit):
			print(f"Skipping own post: {s.title}")
		else:
			threading.Thread(target=handle_submission, args=(s, )).start()


def run_agent(agent_info: AgentInfo, provider: BaseProvider, reddit: praw.Reddit, interactive: bool, iteration_interval: int):
	subreddits = [subreddit.name for subreddit in agent_info.active_on_subreddits]
	stream_submissions_thread = threading.Thread(target=handle_submissions, args=(reddit, subreddits, agent_info, provider))
	stream_submissions_thread.start()
	while True:
		if interactive:
			print('Commands:')
			print("  p=Create a post, i=Show inbox, c=Handle comment, d=Default iteration")
			print("Enter command:")
			command = input()
		else:
			command = "d"

		print(f"Running command: {command}")

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
		elif command == "cs":
			create_submission(reddit, agent_info, provider, interactive)
		else:
			print(f"Invalid command: '{command}'")

		if not interactive:
			time.sleep(iteration_interval)
