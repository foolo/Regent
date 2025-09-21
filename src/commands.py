from dataclasses import dataclass
from src.agent_env import AgentEnv
from src.log_config import logger
from praw import Reddit  # type: ignore
from praw.exceptions import ClientException  # type: ignore
from src.reddit_utils import COMMENT_PREFIX, SUBMISSION_PREFIX


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
				logger.error(f"Error replying to post.")
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
				logger.error(f"Error replying to comment.")
				return {'error': f"Could not reply to comment with ID: {self.content_id}"}
			return {'result': 'Reply posted successfully'}
		else:
			return {'error': f"Invalid content ID: {self.content_id}"}

	@classmethod
	def available(cls, env: AgentEnv) -> bool:
		return env.agent_config.can_reply_to_content
