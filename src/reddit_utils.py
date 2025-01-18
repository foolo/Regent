import os
import yaml
from praw import Reddit  # type: ignore
from praw.models import Comment, Submission, Redditor  # type: ignore
from src.pydantic_models.reddit_config import RedditConfig
from src.log_config import logger

REDDIT_CONFIG_FILENAME = 'config/reddit_config.yaml'


class LoadConfigException(Exception):
	pass


def load_reddit_config():
	if os.path.exists(REDDIT_CONFIG_FILENAME):
		with open(REDDIT_CONFIG_FILENAME) as f:
			config_obj = yaml.safe_load(f)
	else:
		raise LoadConfigException(
		    f"File {REDDIT_CONFIG_FILENAME} not found. Create it by copying {REDDIT_CONFIG_FILENAME}.example to {REDDIT_CONFIG_FILENAME} and filling in the values.")
	config = RedditConfig(**config_obj)
	if not config.user_agent or config.user_agent == "":
		config.user_agent = f"RedditAiAgent"
	if not config.refresh_token or config.refresh_token == "":
		raise LoadConfigException(f"No Reddit refresh token found in {REDDIT_CONFIG_FILENAME}. Run 'python reddit_auth.py' to generate one.")
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


def list_inbox_comments(reddit: Reddit) -> list[Comment]:
	items = reddit.inbox.unread(limit=None)  # type: ignore
	return [i for i in items if isinstance(i, Comment)]


def pop_comment_from_inbox(reddit: Reddit, test_mode: bool) -> Comment | None:
	for comment in list_inbox_comments(reddit):
		if test_mode:
			logger.info(f"Test mode. Not marking comment {comment.id} as read")
		else:
			comment.mark_read()
		return comment
	return None


def show_conversation(reddit: Reddit, comment_id: str) -> list[dict[str, str]]:
	comment = reddit.comment(comment_id)
	root_submission, comments = get_comment_chain(comment, reddit)
	items: list[dict[str, str]] = []
	items.append({
	    'author': get_author_name(root_submission),
	    'title': root_submission.title,
	    'text': root_submission.selftext,
	    'content_id': SUBMISSION_PREFIX + root_submission.id,
	})
	for c in comments:
		items.append({
		    'author': get_author_name(c),
		    'text': c.body,
		    'content_id': COMMENT_PREFIX + c.id,
		})
	return items
