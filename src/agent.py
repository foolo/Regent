from datetime import datetime, timezone
import json
import logging
import os
import threading
import time
from praw import Reddit
from praw.models import Redditor, Comment, Submission
from src.providers.response_models import Action, CreateSubmission, MarkCommentAsRead, ReplyToComment, ShowConversationWithNewActivity, ShowUsername
from src.pydantic_models.agent_state import AgentState, HistoryItem
from src.reddit_utils import get_comment_chain
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_info import AgentInfo

logger = logging.getLogger(__name__)


def get_author_name(item: Comment | Submission) -> str:
	if not item.author:
		return "[unknown/deleted]"
	return item.author.name


def get_latest_submission(current_user: Redditor) -> Submission | None:
	return next(current_user.submissions.new(limit=1))


class Agent:
	def __init__(self, agent_info: AgentInfo, provider: BaseProvider, reddit: Reddit, test_mode: bool, iteration_interval: int):
		self.agent_info = agent_info
		self.provider = provider
		self.reddit = reddit
		self.test_mode = test_mode
		self.iteration_interval = iteration_interval

	def get_current_user(self) -> Redditor:
		current_user = self.reddit.user.me()
		if not current_user:
			raise RuntimeError("No user logged in")
		return current_user

	def list_inbox(self) -> list[dict]:
		inbox = []
		for item in self.reddit.inbox.unread(limit=None):  # type: ignore
			if isinstance(item, Comment):
				inbox.append({
				    'type': 'comment',
				    'id': item.id,
				    'author': get_author_name(item),
				    'body': item.body,
				})
		return inbox

	def pop_comment_from_inbox(self) -> Comment | None:
		for item in self.reddit.inbox.unread(limit=None):  # type: ignore
			if isinstance(item, Comment):
				if self.test_mode:
					print(f"Test mode. Not marking comment {item.id} as read")
				else:
					item.mark_read()
				return item
		return None

	def show_conversation(self, comment_id: str):
		comment = self.reddit.comment(comment_id)
		root_submission, comments = get_comment_chain(comment, self.reddit)
		conversation_struct = {}
		conversation_struct['root_post'] = {'author': get_author_name(root_submission), 'title': root_submission.title, 'text': root_submission.selftext}
		conversation_struct['comments'] = [{'author': get_author_name(comment), 'text': comment.body} for comment in comments]
		return conversation_struct

	def handle_submissions(self, subreddits: list[str]):
		def handle_submission(s: Submission):
			logger.info(f"Handle post from: {s.author}, Title: {s.title}, Text: {s.selftext}")
			system_prompt = [
			    self.agent_info.agent_description + "\n",
			    f"You are looking at a post on Reddit, in the subreddit r/{s.subreddit.display_name}",
			    f"Your task is to first determine whether the post needs a reply.",
			    self.agent_info.behavior.post_reply_needed_classification,
			    "If a reply is needed, set the 'reply_needed' field to true and provide a reply in the 'body' field. Otherwise set the 'reply_needed' field to false and leave the 'body' field undefined.",
			    self.agent_info.behavior.reply_style,
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
			response = self.provider.generate_comment("\n".join(system_prompt), "\n".join(prompt))
			if response is None:
				logger.error("Failed to generate a response")
				return
			logger.info(f"Response:")
			logger.info(response)
			if response.reply_needed:
				if not response.body or response.body == "":
					logger.error("Reply needed but no body provided")
					return
				delay_seconds = self.agent_info.behavior.reply_delay_minutes * 60
				logger.info(f"Posting reply in {delay_seconds} seconds...")
				time.sleep(delay_seconds)
				s.reply(response.body)
				logger.info("Reply posted")

		subreddit = self.reddit.subreddit("+".join(subreddits))
		print(f"Monitoring subreddit: {subreddit.display_name}")
		for s in subreddit.stream.submissions(skip_existing=True):
			if s.author == self.get_current_user():
				print(f"Skipping own post: {s.title}")
			else:
				threading.Thread(target=handle_submission, args=(s, )).start()

	def handle_model_action(self, decision: Action) -> dict:
		if isinstance(decision.command, ShowUsername):
			return {'username': self.get_current_user().name}
		elif isinstance(decision.command, ReplyToComment):
			comment = self.reddit.comment(decision.command.comment_id)
			comment.reply(decision.command.reply)
			return {'result': 'Reply posted successfully'}
		elif isinstance(decision.command, ShowConversationWithNewActivity):
			comment = self.pop_comment_from_inbox()
			if not comment:
				return {'note': 'No new comments in inbox'}
			conversation = self.show_conversation(comment.id)
			return {'conversation': conversation}
		elif isinstance(decision.command, MarkCommentAsRead):
			comment = self.reddit.comment(decision.command.comment_id)
			comment.mark_read()
			return {'result': 'Comment marked as read'}
		elif isinstance(decision.command, CreateSubmission):
			current_user = self.get_current_user()
			latest_submission = get_latest_submission(current_user)
			current_utc = int(time.time())
			min_post_interval_hrs = self.agent_info.behavior.minimum_time_between_posts_hours
			if not latest_submission or current_utc > latest_submission.created_utc + min_post_interval_hrs * 3600:
				self.reddit.subreddit(decision.command.subreddit).submit(decision.command.title, selftext=decision.command.selftext)
				return {'result': 'Submission created'}
			else:
				return {
				    'error':
				    f"Not enough time has passed since the last post, which was published {datetime.fromtimestamp(latest_submission.created_utc)}. Minimum time between posts is {min_post_interval_hrs} hours."
				}
		else:
			return {'error': 'Invalid command'}

	def generate_dashboard(self):
		unread_messages = len(self.list_inbox())
		return "\n".join([
		    f"Unread messages in inbox: {unread_messages}",
		])

	def run(self):
		# subreddits = [subreddit.name for subreddit in agent_info.active_on_subreddits]
		# stream_submissions_thread = threading.Thread(target=handle_submissions, args=(reddit, subreddits, agent_info, provider))
		# stream_submissions_thread.start()

		agent_state_filename = 'agent_state.json'
		if os.path.exists(agent_state_filename):
			with open(agent_state_filename) as f:
				whole_file_as_string = f.read()
				state = AgentState.model_validate_json(whole_file_as_string)
		else:
			state = AgentState(history=[])

		system_prompt = "\n".join([
		    self.agent_info.agent_description,
		    "",
		    "To acheive your goals, you can interact with Reddit users by replying to comments, creating posts, and more.",
		    "You will be provided with a list of available commands, the recent command history, and a dashboard of the current state (e.g. number of messages in inbox).",
		    "Respond with the command and parameters you want to execute. Also provide a motivation behind the action, and any future steps you plan to take, to help keep track of your strategy.",
		    "You can work in many steps, and the system will remember your previous actions and responses.",
		    "Only use comment IDs you have received from earlier actions. Don't use random comment IDs. If you don't have any comment IDs, you can use the 'show_inbox' command to get some.",
		    "If you want to see the whole conversation from the root post to a comment, use the 'show_conversation_for_comment' command with the comment ID.",
		    "",
		    "Available commands:",
		    "  show_my_username  # Show your username",
		    "  mark_comment_as_read COMMENT_ID  # Mark a comment as read",
		    "  show_conversation_with_new_activity  # If you have new comments in your inbox, show the whole conversation for the newest one",
		    "  reply_to_comment COMMENT_ID REPLY  # Reply to a comment with the given ID. You can get the comment IDs from the inbox",
		    "  create_post SUBREDDIT TITLE TEXT  # Create a post in the given subreddit (excluding 'r/') with the given title and text",
		])

		print("System prompt:")
		print(system_prompt)

		while True:
			print("Prompt:")
			if len(state.history) == 0:
				print("(No history)")
			else:
				print(state.history[-1].action_result)

			dashboard_message = "\n".join([
			    "Dashboard:",
			    self.generate_dashboard(),
			    "",
			    "Now you can enter your action:",
			])

			print("Dashboard message:")
			print(dashboard_message)

			model_action = self.provider.get_action(system_prompt, state.history, dashboard_message)
			if model_action is None:
				logger.error("Failed to get action")
				continue

			print("")
			print(f"Model action: {model_action.command.literal}")
			print(model_action.model_dump())

			if self.test_mode:
				input("Press enter to continue...")
			else:
				time.sleep(self.iteration_interval)

			action_result = self.handle_model_action(model_action)

			state.history.append(HistoryItem(
			    model_action=json.dumps(model_action.model_dump()),
			    action_result=json.dumps(action_result),
			))

			with open(agent_state_filename, 'w') as f:
				f.write(state.model_dump_json(indent=2))
