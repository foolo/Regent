from dataclasses import dataclass
import time
from src.agent_env import AgentEnv
from src.log_config import logger
from praw import Reddit  # type: ignore
from praw.exceptions import ClientException  # type: ignore
from src.pydantic_models.agent_config import AgentConfig
from src.reddit_utils import COMMENT_PREFIX, SUBMISSION_PREFIX, get_current_user, get_latest_submission
from src.utils import seconds_to_hms


@dataclass
class ReplyToContent:
	content_id: str
	reply_text: str

	def execute(self, env: AgentEnv):
		if self.content_id.startswith(SUBMISSION_PREFIX):
			try:
				submission_id = self.content_id[len(SUBMISSION_PREFIX):]
				submission = env.reddit.submission(submission_id)
				submission.title  # Check if submission exists
			except Exception:
				return {'error': f"Could not fetch post with ID: {self.content_id}"}
			try:
				submission.reply(self.reply_text)
			except Exception:
				logger.exception(f"Error replying to post.")
				return {'error': f"Could not reply to post with ID: {self.content_id}"}
			return {'result': 'Reply posted successfully'}
		elif self.content_id.startswith(COMMENT_PREFIX):
			try:
				comment_id = self.content_id[len(COMMENT_PREFIX):]
				comment = env.reddit.comment(comment_id)
				comment.refresh()
			except ClientException:
				return {'error': f"Could not fetch comment with ID: {self.content_id}"}
			try:
				comment.reply(self.reply_text)
			except Exception:
				logger.exception(f"Error replying to comment.")
				return {'error': f"Could not reply to comment with ID: {self.content_id}"}
			return {'result': 'Reply posted successfully'}
		else:
			return {'error': f"Invalid content ID: {self.content_id}"}

	@classmethod
	def available(cls, env: AgentEnv) -> bool:
		return env.agent_config.can_reply_to_content


def seconds_since_last_post(reddit: Reddit, agent_config: AgentConfig) -> int:
	current_user = get_current_user(reddit)
	latest_submission = get_latest_submission(current_user)
	if not latest_submission:
		return 0
	current_utc = int(time.time())
	return max(current_utc - int(latest_submission.created_utc), 0)


@dataclass
class CreatePost:
	subreddit: str
	post_title: str
	post_text: str

	def execute(self, env: AgentEnv):
		try:
			time_left = env.agent_config.minimum_time_between_posts_hours * 3600 - seconds_since_last_post(env.reddit, env.agent_config)
			if time_left <= 0:
				if not self.subreddit in [s.lower() for s in env.agent_config.active_on_subreddits]:
					return {'error': f"You are not active on the subreddit: {self.subreddit}"}
				env.reddit.subreddit(self.subreddit).submit(self.post_title, selftext=self.post_text)
				return {'result': 'Post created'}
			else:
				return {'error': f"Not enough time has passed since the last post. Time until next post possible: {seconds_to_hms(int(time_left))}"}
		except Exception:
			logger.exception(f"Error creating post.")
			return {'error': 'Could not create post'}

	@classmethod
	def available(cls, env: AgentEnv) -> bool:
		if not env.agent_config.can_create_posts:
			return False
		if env.test_mode:
			return True
		return seconds_since_last_post(env.reddit, env.agent_config) >= env.agent_config.minimum_time_between_posts_hours * 3600
