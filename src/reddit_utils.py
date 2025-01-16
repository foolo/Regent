import os
from typing import Any
import yaml
from praw import Reddit  # type: ignore
from praw.models import Comment, Submission, Redditor  # type: ignore
from src.pydantic_models.reddit_config import RedditConfig
from src.log_config import logger

REDDIT_CONFIG_FILENAME = 'config/reddit_config.yaml'


def load_reddit_config():
	if os.path.exists(REDDIT_CONFIG_FILENAME):
		with open(REDDIT_CONFIG_FILENAME) as f:
			config_obj = yaml.safe_load(f)
	else:
		raise FileNotFoundError(
		    f"File {REDDIT_CONFIG_FILENAME} not found. Create it by copying {REDDIT_CONFIG_FILENAME}.example to {REDDIT_CONFIG_FILENAME} and filling in the values.")
	config = RedditConfig(**config_obj)
	if not config.user_agent or config.user_agent == "":
		config.user_agent = f"RedditAiAgent"
	return config


COMMENT_PREFIX = 't1_'
SUBMISSION_PREFIX = 't3_'


def get_comment_chain(comment: Comment, reddit: Reddit) -> tuple[Submission, list[Comment]]:
	if comment.parent_id.startswith(COMMENT_PREFIX):
		parent_comment = reddit.comment(id=comment.parent_id)
		root_submission, comments = get_comment_chain(parent_comment, reddit)
		return root_submission, comments + [comment]
	elif comment.parent_id.startswith(SUBMISSION_PREFIX):
		id_without_prefix = comment.parent_id[len(SUBMISSION_PREFIX):]
		submission = reddit.submission(id=id_without_prefix)
		return submission, [comment]
	else:
		raise ValueError(f"Invalid parent_id: {comment.parent_id}")


def get_author_name(item: Comment | Submission) -> str:
	if not item.author:
		return "[unknown/deleted]"
	return item.author.name


def get_latest_submission(current_user: Redditor) -> Submission | None:
	submissions_iter = current_user.submissions.new(limit=1)
	return next(submissions_iter)


def get_current_user(reddit: Reddit) -> Redditor:
	current_user = reddit.user.me()
	if not current_user:
		raise RuntimeError("No user logged in")
	return current_user


def pop_comment_from_inbox(reddit: Reddit, test_mode: bool) -> Comment | None:
	for item in reddit.inbox.unread(limit=None):  # type: ignore
		if isinstance(item, Comment):
			if test_mode:
				logger.info(f"Test mode. Not marking comment {item.id} as read")
			else:
				item.mark_read()
			return item
	return None


def show_conversation(reddit: Reddit, comment_id: str) -> dict[str, Any]:
	comment = reddit.comment(comment_id)
	root_submission, comments = get_comment_chain(comment, reddit)
	conversation_struct: dict[str, Any] = {}
	conversation_struct['root_post'] = {
	    'author': get_author_name(root_submission),
	    'title': root_submission.title,
	    'text': root_submission.selftext,
	}
	conversation_struct['comments'] = [{
	    'author': get_author_name(comment),
	    'text': comment.body,
	    'content_id': COMMENT_PREFIX + comment.id,
	} for comment in comments]

	return conversation_struct


def list_inbox(reddit: Reddit) -> list[dict[str, str]]:
	inbox: list[dict[str, str]] = []
	for item in reddit.inbox.unread(limit=None):  # type: ignore
		if isinstance(item, Comment):
			inbox.append({
			    'type': 'comment',
			    'content_id': COMMENT_PREFIX + item.id,
			    'author': get_author_name(item),
			    'body': item.body,
			})
	return inbox
