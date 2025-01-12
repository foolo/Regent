import os
import yaml
from praw import Reddit  # type: ignore
from praw.models import Comment, Submission  # type: ignore
from src.pydantic_models.reddit_config import RedditConfig

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


comment_prefix = 't1_'
submission_prefix = 't3_'


def get_comment_chain(comment: Comment, reddit: Reddit) -> tuple[Submission, list[Comment]]:
	if comment.parent_id.startswith(comment_prefix):
		parent_comment = reddit.comment(id=comment.parent_id)
		root_submission, comments = get_comment_chain(parent_comment, reddit)
		return root_submission, comments + [comment]
	elif comment.parent_id.startswith(submission_prefix):
		id_without_prefix = comment.parent_id[len(submission_prefix):]
		submission = reddit.submission(id=id_without_prefix)
		return submission, [comment]
	else:
		raise ValueError(f"Invalid parent_id: {comment.parent_id}")
