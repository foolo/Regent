from datetime import datetime, timedelta, timezone
import json
import logging
import os
import queue
import sys
import threading
import time
from praw import Reddit
from praw.models import Redditor, Comment, Submission
from praw.exceptions import ClientException
from prawcore.exceptions import ServerError
from src.providers.response_models import Action, CreatePost, ReplyToComment, ReplyToPost, ShowConversationWithNewActivity, ShowNewPost, ShowUsername
from src.pydantic_models.agent_state import AgentState, HistoryItem, StreamedSubmission
from src.reddit_utils import get_comment_chain
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_config import AgentConfig

logger = logging.getLogger(__name__)


def get_author_name(item: Comment | Submission) -> str:
	if not item.author:
		return "[unknown/deleted]"
	return item.author.name


def get_latest_submission(current_user: Redditor) -> Submission | None:
	return next(current_user.submissions.new(limit=1))


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
				    'comment_id': item.id,
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
		conversation_struct['root_post'] = {
		    'author': get_author_name(root_submission),
		    'title': root_submission.title,
		    'text': root_submission.selftext,
		}
		conversation_struct['comments'] = [{
		    'author': get_author_name(comment),
		    'text': comment.body,
		    'comment_id': comment.id,
		} for comment in comments]

		return conversation_struct

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
			submissions_newer_than_max_age = []
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
			if s.author == self.get_current_user():
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

	def handle_model_action(self, decision: Action) -> dict:
		if isinstance(decision.command, ShowUsername):
			try:
				username = self.get_current_user().name
			except Exception as e:
				logger.exception(f"Error getting username. Exception: {e}")
				return {'error': 'Could not get username'}
			return {'username': username}
		elif isinstance(decision.command, ShowNewPost):
			try:
				self.stream_submissions_to_state()
				if len(self.state.streamed_submissions) == 0:
					return {'note': 'No new submissions'}

				latest_submission = self.reddit.submission(self.state.streamed_submissions[-1].id)
				del self.state.streamed_submissions[-1]
				return {
				    'post': {
				        'post_id': latest_submission.id,
				        'author': get_author_name(latest_submission),
				        'title': latest_submission.title,
				        'text': latest_submission.selftext,
				    }
				}
			except Exception as e:
				logger.exception(f"Error fetching new post. Exception: {e}")
				return {'error': 'Could not fetch new post'}
		elif isinstance(decision.command, ReplyToPost):
			try:
				submission = self.reddit.submission(decision.command.post_id)
				submission.title  # Check if submission exists
			except ServerError as e:
				return {'error': f"Could not fetch post with ID: {decision.command.post_id}"}
			try:
				submission.reply(decision.command.reply_text)
			except Exception as e:
				logger.exception(f"Error replying to post. Exception: {e}")
				return {'error': f"Could not reply to post with ID: {decision.command.post_id}"}
			return {'result': 'Reply posted successfully'}
		elif isinstance(decision.command, ReplyToComment):
			try:
				comment = self.reddit.comment(decision.command.comment_id)
				comment.refresh()
			except ClientException as e:
				return {'error': f"Could not fetch comment with ID: {decision.command.comment_id}"}
			try:
				comment.reply(decision.command.reply_text)
			except Exception as e:
				logger.exception(f"Error replying to comment. Exception: {e}")
				return {'error': f"Could not reply to comment with ID: {decision.command.comment_id}"}
			return {'result': 'Reply posted successfully'}
		elif isinstance(decision.command, ShowConversationWithNewActivity):
			try:
				comment = self.pop_comment_from_inbox()
				if not comment:
					return {'note': 'No new comments in inbox'}
				conversation = self.show_conversation(comment.id)
			except Exception as e:
				logger.exception(f"Error showing conversation. Exception: {e}")
				return {'error': f"Could not show conversation"}
			return {'conversation': conversation}
		elif isinstance(decision.command, CreatePost):
			try:
				current_user = self.get_current_user()
				latest_submission = get_latest_submission(current_user)
				current_utc = int(time.time())
				min_post_interval_hrs = self.agent_config.behavior.minimum_time_between_posts_hours
				if not latest_submission or current_utc > latest_submission.created_utc + min_post_interval_hrs * 3600:
					self.reddit.subreddit(decision.command.subreddit).submit(decision.command.post_title, selftext=decision.command.post_text)
					return {'result': 'Post created'}
				else:
					return {
					    'error':
					    f"Not enough time has passed since the last post, which was published {datetime.fromtimestamp(latest_submission.created_utc)}. Minimum time between posts is {min_post_interval_hrs} hours."
					}
			except Exception as e:
				logger.exception(f"Error creating post. Exception: {e}")
				return {'error': 'Could not create post'}
		else:
			return {'error': 'Invalid command'}

	def generate_dashboard(self):
		unread_messages = len(self.list_inbox())
		return "\n".join([
		    f"Unread messages in inbox: {unread_messages}",
		])

	def save_state(self):
		with open(self.state_filename, 'w') as f:
			f.write(self.state.model_dump_json(indent=2))

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
		    "Only use comment IDs you have received from earlier actions. Don't use random comment IDs. If you don't have any comment IDs, you can use the 'show_inbox' command to get some.",
		    "If you want to see the whole conversation from the root post to a comment, use the 'show_conversation_for_comment' command with the comment ID.",
		    "",
		    "Available commands:",
		    "  show_my_username  # Show your username",
		    "  show_new_post  # Show the newest post in the monitored subreddits",
		    "  reply_to_post POST_ID REPLY_TEXT  # Reply to a post with the given ID. You can get the post IDs via the 'show_new_post' command",
		    "  show_conversation_with_new_activity  # If you have new comments in your inbox, show the whole conversation for the newest one",
		    "  reply_to_comment COMMENT_ID REPLY_TEXT  # Reply to a comment with the given ID. You can get the comment IDs from the inbox",
		    "  create_post SUBREDDIT POST_TITLE POST_TEXT  # Create a post in the given subreddit (excluding 'r/') with the given title and text",
		])

		print("System prompt:")
		print(system_prompt)

		while True:
			print("Prompt:")
			if len(self.state.history) == 0:
				print("(No history)")
			else:
				print(self.state.history[-1].action_result)

			dashboard_message = "\n".join([
			    "Dashboard:",
			    self.generate_dashboard(),
			    "",
			    "Now you can enter your action:",
			])

			print("Dashboard message:")
			print(dashboard_message)

			model_action = self.provider.get_action(system_prompt, self.state.history, dashboard_message)
			if model_action is None:
				logger.error("Failed to get action")
				continue

			print("")
			print(f"Model action: {model_action.command.literal}")
			print(model_action.model_dump())

			if self.test_mode:
				print("Press enter to continue...", file=sys.stderr)
				input("")
			else:
				time.sleep(self.iteration_interval)

			action_result = self.handle_model_action(model_action)

			self.state.history.append(
			    HistoryItem(
			        model_action=json.dumps(model_action.model_dump(), ensure_ascii=False),
			        action_result=json.dumps(action_result, ensure_ascii=False),
			    ))

			self.save_state()
