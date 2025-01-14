from dataclasses import dataclass
from datetime import datetime
import time
from typing import Any, Dict, List, Type
from src.log_config import logger
from praw import Reddit  # type: ignore
from praw.exceptions import ClientException  # type: ignore
from abc import abstractmethod
from src.providers.base_provider import Action
from src.pydantic_models.agent_config import AgentConfig
from src.pydantic_models.agent_state import AgentState
from src.reddit_utils import COMMENT_PREFIX, SUBMISSION_PREFIX, get_author_name, get_current_user, get_latest_submission, pop_comment_from_inbox, show_conversation


@dataclass
class AgentEnv:
	reddit: Reddit
	agent_state: AgentState
	agent_config: AgentConfig
	test_mode: bool


class Command:
	registry: Dict[str, Type['Command']] = {}

	@classmethod
	def register(cls, name: str):
		def decorator(command_cls: Type['Command']):
			cls.registry[name] = command_cls
			return command_cls

		return decorator

	@classmethod
	def decode(cls, action: Action) -> 'Command':
		if action.command not in cls.registry:
			raise ValueError(f"Unknown command: {action.command}")

		command_cls = cls.registry[action.command]
		return command_cls.instance_decode(action.parameters)

	@classmethod
	def instance_decode(cls, args: List[str]) -> 'Command':
		raise NotImplementedError("Decode method must be implemented by subclasses")

	@abstractmethod
	def execute(self, env: AgentEnv) -> dict[str, Any]:
		pass


@Command.register("show_username")
@dataclass
class ShowUsername(Command):
	@classmethod
	def instance_decode(cls, args: List[str]) -> 'ShowUsername':
		if len(args) != 0:
			raise ValueError(f"show_username requires 0 arguments, got {len(args)}")
		return cls()

	def execute(self, env: AgentEnv):
		try:
			username = get_current_user(env.reddit).name
		except Exception as e:
			logger.exception(f"Error getting username. Exception: {e}")
			return {'error': 'Could not get username'}
		return {'username': username}


@Command.register("show_new_post")
@dataclass
class ShowNewPost(Command):
	@classmethod
	def instance_decode(cls, args: List[str]) -> 'ShowNewPost':
		if len(args) != 0:
			raise ValueError(f"show_new_post requires 0 arguments, got {len(args)}")
		return cls()

	def execute(self, env: AgentEnv) -> dict[str, Any]:
		try:
			if len(env.agent_state.streamed_submissions) == 0:
				return {'note': 'No new submissions'}

			latest_submission = env.reddit.submission(env.agent_state.streamed_submissions[-1].id)
			del env.agent_state.streamed_submissions[-1]
			return {
			    'post': {
			        'content_id': SUBMISSION_PREFIX + latest_submission.id,
			        'author': get_author_name(latest_submission),
			        'title': latest_submission.title,
			        'text': latest_submission.selftext,
			    }
			}
		except Exception as e:
			logger.exception(f"Error fetching new post. Exception: {e}")
			return {'error': 'Could not fetch new post'}


@Command.register("show_conversation_with_new_activity")
@dataclass
class ShowConversationWithNewActivity(Command):
	@classmethod
	def instance_decode(cls, args: List[str]) -> 'ShowConversationWithNewActivity':
		if len(args) != 0:
			raise ValueError(f"show_conversation_with_new_activity requires 0 arguments, got {len(args)}")
		return cls()

	def execute(self, env: AgentEnv) -> dict[str, Any]:
		try:
			comment = pop_comment_from_inbox(env.reddit, env.test_mode)
			if not comment:
				return {'note': 'No new comments in inbox'}
			conversation = show_conversation(env.reddit, comment.id)
		except Exception as e:
			logger.exception(f"Error showing conversation. Exception: {e}")
			return {'error': f"Could not show conversation"}
		return {'conversation': conversation}


@Command.register("reply_to_content")
@dataclass
class ReplyToContent(Command):
	content_id: str
	reply_text: str

	@classmethod
	def instance_decode(cls, args: List[str]) -> 'ShowUsername':
		if len(args) != 2:
			raise ValueError(f"show_username requires 2 arguments, got {len(args)}")
		return cls(content_id=args[0], reply_text=args[1])

	def execute(self, env: AgentEnv):
		if self.content_id.startswith(SUBMISSION_PREFIX):
			try:
				submission_id = self.content_id[len(SUBMISSION_PREFIX):]
				submission = env.reddit.submission(submission_id)
				submission.title  # Check if submission exists
			except Exception as e:
				return {'error': f"Could not fetch post with ID: {self.content_id}"}
			try:
				submission.reply(self.reply_text)
			except Exception as e:
				logger.exception(f"Error replying to post. Exception: {e}")
				return {'error': f"Could not reply to post with ID: {self.content_id}"}
			return {'result': 'Reply posted successfully'}
		elif self.content_id.startswith(COMMENT_PREFIX):
			try:
				comment_id = self.content_id[len(COMMENT_PREFIX):]
				comment = env.reddit.comment(comment_id)
				comment.refresh()
			except ClientException as e:
				return {'error': f"Could not fetch comment with ID: {self.content_id}"}
			try:
				comment.reply(self.reply_text)
			except Exception as e:
				logger.exception(f"Error replying to comment. Exception: {e}")
				return {'error': f"Could not reply to comment with ID: {self.content_id}"}
			return {'result': 'Reply posted successfully'}
		else:
			return {'error': f"Invalid content ID: {self.content_id}"}


@Command.register("create_post")
@dataclass
class CreatePost(Command):
	subreddit: str
	post_title: str
	post_text: str

	@classmethod
	def instance_decode(cls, args: List[str]) -> 'CreatePost':
		if len(args) != 3:
			raise ValueError(f"create_post requires 3 arguments, got {len(args)}")
		return cls(subreddit=args[0], post_title=args[1], post_text=args[2])

	def execute(self, env: AgentEnv):
		try:
			current_user = get_current_user(env.reddit)
			latest_submission = get_latest_submission(current_user)
			current_utc = int(time.time())
			min_post_interval_hrs = env.agent_config.behavior.minimum_time_between_posts_hours
			if not latest_submission or current_utc > latest_submission.created_utc + min_post_interval_hrs * 3600:
				env.reddit.subreddit(self.subreddit).submit(self.post_title, selftext=self.post_text)
				return {'result': 'Post created'}
			else:
				return {
				    'error':
				    f"Not enough time has passed since the last post, which was published {datetime.fromtimestamp(latest_submission.created_utc)}. Minimum time between posts is {min_post_interval_hrs} hours."
				}
		except Exception as e:
			logger.exception(f"Error creating post. Exception: {e}")
			return {'error': 'Could not create post'}
