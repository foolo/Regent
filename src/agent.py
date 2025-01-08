from datetime import datetime
import json
import logging
import random
import threading
import time
from praw import Reddit
from praw.models import Redditor, Comment, Submission, Message
from src.history import History, HistoryTurn
from src.providers.response_models import ActionDecision, MarkCommentAsReadCommand, ReplyToCommentCommand, ShowConversationForCommentCommand, ShowInboxCommand, ShowUsernameCommand
from src.reddit_utils import get_comment_chain
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_info import ActiveOnSubreddit, AgentInfo

logger = logging.getLogger(__name__)


def get_current_user(reddit: Reddit) -> Redditor:
	current_user = reddit.user.me()
	if not current_user:
		raise RuntimeError("No user logged in")
	return current_user


def get_author_name(item: Comment | Submission) -> str:
	if not item.author:
		return "[unknown/deleted]"
	return item.author.name


def list_inbox(reddit: Reddit) -> list[dict]:
	inbox = []
	for item in reddit.inbox.unread(limit=None):  # type: ignore
		if isinstance(item, Comment):
			inbox.append({
			    'type': 'comment',
			    'id': item.id,
			    'author': get_author_name(item),
			    'body': item.body,
			})
	return inbox


def show_conversation(reddit: Reddit, comment_id: str):
	comment = reddit.comment(comment_id)
	root_submission, comments = get_comment_chain(comment, reddit)
	conversation_struct = {}
	conversation_struct['root_post'] = {'author': get_author_name(root_submission), 'title': root_submission.title, 'text': root_submission.selftext}
	conversation_struct['comments'] = [{'author': get_author_name(comment), 'text': comment.body} for comment in comments]
	return conversation_struct


def select_subreddit(agent_info: AgentInfo) -> ActiveOnSubreddit:
	return random.choice(agent_info.active_on_subreddits)


def create_submission(reddit: Reddit, agent_info: AgentInfo, provider: BaseProvider, interactive: bool):
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


def get_latest_submission(current_user: Redditor) -> Submission | None:
	return next(current_user.submissions.new(limit=1))


def create_submission_if_time(reddit: Reddit, agent_info: AgentInfo, provider: BaseProvider, interactive: bool):
	current_user = get_current_user(reddit)
	latest_submission = get_latest_submission(current_user)
	current_utc = int(time.time())
	if not latest_submission or current_utc > latest_submission.created_utc + agent_info.behavior.minimum_time_between_posts_hours * 3600:
		create_submission(reddit, agent_info, provider, interactive)
	else:
		logger.info(f"Not enough time has passed since the last post, which was published {datetime.fromtimestamp(latest_submission.created_utc)}")


def handle_submissions(reddit: Reddit, subreddits: list[str], agent_info: AgentInfo, provider: BaseProvider):
	def handle_submission(s: Submission):
		logger.info(f"Handle post from: {s.author}, Title: {s.title}, Text: {s.selftext}")
		system_prompt = [
		    agent_info.agent_description + "\n",
		    f"You are looking at a post on Reddit, in the subreddit r/{s.subreddit.display_name}",
		    f"Your task is to first determine whether the post needs a reply.",
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
			delay_seconds = agent_info.behavior.reply_delay_minutes * 60
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


def handle_model_decision(decision: ActionDecision, reddit: Reddit, agent_info: AgentInfo, provider: BaseProvider, history: History) -> dict:
	if isinstance(decision.command, ShowInboxCommand):
		inbox = list_inbox(reddit)
		return {'inbox': inbox}
	elif isinstance(decision.command, ShowUsernameCommand):
		return {'username': get_current_user(reddit).name}
	elif isinstance(decision.command, ReplyToCommentCommand):
		comment = reddit.comment(decision.command.comment_id)
		comment.reply(decision.command.reply)
		return {'result': 'Reply posted successfully'}
	elif isinstance(decision.command, ShowConversationForCommentCommand):
		conversation = show_conversation(reddit, decision.command.comment_id)
		return {'conversation': conversation}
	elif isinstance(decision.command, MarkCommentAsReadCommand):
		comment = reddit.comment(decision.command.comment_id)
		comment.mark_read()
		return {'result': 'Comment marked as read'}
	else:
		return {'error': 'Invalid command'}


def run_agent(agent_info: AgentInfo, provider: BaseProvider, reddit: Reddit, interactive: bool, iteration_interval: int):
	# subreddits = [subreddit.name for subreddit in agent_info.active_on_subreddits]
	# stream_submissions_thread = threading.Thread(target=handle_submissions, args=(reddit, subreddits, agent_info, provider))
	# stream_submissions_thread.start()

	history = History()

	initial_user_prompt = [
	    "To acheive your goals, you can interact with Reddit users by replying to comments, creating posts, and more.",
	    "Respond with the command and parameters you want to execute. Also provide a motivation behind the action, and any future steps you plan to take, to help keep track of your strategy.",
	    "You can work in many steps, and the system will remember your previous actions and responses.",
	    "Only use comment IDs you have received from earlier actions. Don't use random comment IDs. If you don't have any comment IDs, you can use the 'show_inbox' command to get some.",
	    "If you want to see the whole conversation from the root post to a comment, use the 'show_conversation_for_comment' command with the comment ID.",
	    "",
	    "Available commands:",
	    "  show_my_username  # Show your username",
	    "  show_inbox   # List all unread messages and comments",
	    "  mark_comment_as_read COMMENT_ID  # Mark a comment as read",
	    "  show_conversation_for_comment  COMMENT_ID  # Show the conversation from the root post to the comment with the given ID",
	    "  reply_to_comment COMMENT_ID REPLY  # Reply to a comment with the given ID. You can get the comment IDs from the inbox",
	]
	message_to_model = "\n".join(initial_user_prompt)

	system_prompt = agent_info.agent_description
	print("System prompt:")
	print(system_prompt)

	while True:
		if isinstance(message_to_model, dict):
			message_to_model = json.dumps(message_to_model)

		print("User prompt:")
		print(message_to_model)
		response = provider.get_action(system_prompt, history, message_to_model)
		if response is None:
			logger.error("Failed to get action")
			continue

		history.turns.append(HistoryTurn(user_prompt=message_to_model, response=json.dumps(response.model_dump())))

		print("")
		print(f"Action decision: {response.command.literal}")
		print(response.model_dump())
		message_to_model = handle_model_decision(response, reddit, agent_info, provider, history)

		input("Press enter to continue...")
