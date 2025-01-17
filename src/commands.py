from dataclasses import dataclass
import time
from typing import Any, Type
from src.log_config import logger
from praw import Reddit  # type: ignore
from praw.exceptions import ClientException  # type: ignore
from abc import abstractmethod
from src.providers.base_provider import Action
from src.pydantic_models.agent_config import AgentConfig
from src.pydantic_models.agent_state import AgentState
from src.reddit_utils import COMMENT_PREFIX, SUBMISSION_PREFIX, get_author_name, get_current_user, get_latest_submission, list_inbox, pop_comment_from_inbox, show_conversation
from src.utils import seconds_to_dhms


@dataclass
class AgentEnv:
	reddit: Reddit
	agent_state: AgentState
	agent_config: AgentConfig
	test_mode: bool


@dataclass
class CommandInfo:
	command: Type['Command']
	parameter_names: list[str]
	description: str


class Command:
	registry: dict[str, CommandInfo] = {}

	@classmethod
	def register(cls, name: str, parameter_names: list[str], description: str):
		def decorator(command_cls: Type['Command']):
			cls.registry[name] = CommandInfo(command=command_cls, parameter_names=parameter_names, description=description)
			return command_cls

		return decorator

	@classmethod
	def decode(cls, action: Action) -> 'Command':
		if action.command not in cls.registry:
			raise ValueError(f"Unknown command: {action.command}")

		command_cls = cls.registry[action.command]
		return command_cls.command.instance_decode(action.parameters)

	@classmethod
	def instance_decode(cls, args: list[str]) -> 'Command':
		raise NotImplementedError("Decode method must be implemented by subclasses")

	@abstractmethod
	def execute(self, env: AgentEnv) -> dict[str, Any]:
		pass

	@classmethod
	def available(cls, env: AgentEnv) -> bool:
		raise NotImplementedError("Available method must be implemented by subclasses")


@Command.register("show_new_post", [], "Show the newest post in the monitored subreddits")
@dataclass
class ShowNewPost(Command):
	@classmethod
	def instance_decode(cls, args: list[str]) -> 'ShowNewPost':
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

	@classmethod
	def available(cls, env: AgentEnv) -> bool:
		return len(env.agent_state.streamed_submissions) > 0


@Command.register("show_conversation_with_new_activity", [], "If you have new comments in your inbox, show the whole conversation for the newest one")
@dataclass
class ShowConversationWithNewActivity(Command):
	@classmethod
	def instance_decode(cls, args: list[str]) -> 'ShowConversationWithNewActivity':
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

	@classmethod
	def available(cls, env: AgentEnv) -> bool:
		return len(list_inbox(env.reddit)) > 0


@Command.register("reply_to_content", ['CONTENT_ID', 'REPLY_TEXT'],
                  "Reply to a post or comment with the given ID. You can get comment IDs from the inbox, and post IDs from the 'show_new_post' command")
@dataclass
class ReplyToContent(Command):
	content_id: str
	reply_text: str

	@classmethod
	def instance_decode(cls, args: list[str]) -> 'ReplyToContent':
		if len(args) != 2:
			raise ValueError(f"reply_to_content requires 2 arguments, got {len(args)}")
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

	@classmethod
	def available(cls, env: AgentEnv) -> bool:
		return True


def time_until_create_post_possible(reddit: Reddit, agent_config: AgentConfig) -> int:
	current_user = get_current_user(reddit)
	latest_submission = get_latest_submission(current_user)
	if not latest_submission:
		return 0
	current_utc = int(time.time())
	min_post_interval_hrs = agent_config.minimum_time_between_posts_hours
	return int(max(latest_submission.created_utc + min_post_interval_hrs * 3600 - current_utc, 0))


@Command.register("create_post", ['SUBREDDIT', 'POST_TITLE', 'POST_TEXT'], "Create a post in the given subreddit (excluding 'r/') with the given title and text")
@dataclass
class CreatePost(Command):
	subreddit: str
	post_title: str
	post_text: str

	@classmethod
	def instance_decode(cls, args: list[str]) -> 'CreatePost':
		if len(args) != 3:
			raise ValueError(f"create_post requires 3 arguments, got {len(args)}")
		return cls(subreddit=args[0], post_title=args[1], post_text=args[2])

	def execute(self, env: AgentEnv):
		try:
			time_left = time_until_create_post_possible(env.reddit, env.agent_config)
			if time_left <= 0:
				if not self.subreddit in env.agent_config.active_on_subreddits:
					return {'error': f"You are not active on the subreddit: {self.subreddit}"}
				env.reddit.subreddit(self.subreddit).submit(self.post_title, selftext=self.post_text)
				return {'result': 'Post created'}
			else:
				return {'error': f"Not enough time has passed since the last post. Time until next post possible: {seconds_to_dhms(time_left)}"}
		except Exception as e:
			logger.exception(f"Error creating post. Exception: {e}")
			return {'error': 'Could not create post'}

	@classmethod
	def available(cls, env: AgentEnv) -> bool:
		return time_until_create_post_possible(env.reddit, env.agent_config) <= 0
