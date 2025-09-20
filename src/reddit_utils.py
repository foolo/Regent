from dataclasses import dataclass, field
import os
from typing import Any
import yaml
from praw import Reddit  # type: ignore
from praw.models import Comment, Submission, Redditor, MoreComments  # type: ignore
from praw.models.comment_forest import CommentForest  # type: ignore
from src.pydantic_models.reddit_config import RedditConfig

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
		config.user_agent = f"Regent"
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


def show_conversation(reddit: Reddit, comment_id: str) -> list[dict[str, str]]:
	comment = reddit.comment(comment_id)
	root_submission, comments = get_comment_chain(comment, reddit)
	items: list[dict[str, str]] = []
	items.append({
	    'content_id': SUBMISSION_PREFIX + root_submission.id,
	    'author': get_author_name(root_submission),
	    'title': root_submission.title,
	    'text': root_submission.selftext,
	})
	for c in comments:
		items.append({
		    'content_id': COMMENT_PREFIX + c.id,
		    'author': get_author_name(c),
		    'text': c.body,
		})
	return items


@dataclass
class SubmissionTreeNode:
	subreddit: str
	author: str
	title: str
	text: str
	content_id: str
	replies: list['CommentTreeNode'] = field(default_factory=list)  # type: ignore

	def to_dict(self) -> dict[str, Any]:
		return {
		    'content_id': self.content_id,
		    'subreddit': self.subreddit,
		    'author': self.author,
		    'title': self.title,
		    'text': self.text,
		    'replies': [r.to_dict() for r in self.replies],
		}


@dataclass
class CommentTreeNode:
	author: str
	text: str
	content_id: str
	score: int
	replies: list['CommentTreeNode'] = field(default_factory=list)  # type: ignore

	def to_dict(self) -> dict[str, Any]:
		return {
		    'content_id': self.content_id,
		    'author': self.author,
		    'text': self.text,
		    'score': self.score,
		    'replies': [r.to_dict() for r in self.replies],
		}


def get_comment_tree_recursive(comments: CommentForest) -> list[CommentTreeNode]:
	items: list[CommentTreeNode] = []
	for comment in comments:
		if isinstance(comment, MoreComments):
			continue
		elif isinstance(comment, Comment):  # type: ignore
			is_deleted = comment.author is None
			if is_deleted:
				continue
			items.append(
			    CommentTreeNode(
			        author=get_author_name(comment),
			        text=comment.body,
			        content_id=COMMENT_PREFIX + comment.id,
			        score=comment.score,
			        replies=get_comment_tree_recursive(comment.replies),
			    ))
	return items


def get_tree_size(min_score_threshold: int | None, tree: list[CommentTreeNode]) -> int:
	size = 0
	for node in tree:
		if min_score_threshold is not None and node.score < min_score_threshold:
			continue
		size += 1 + get_tree_size(min_score_threshold, node.replies)
	return size


def find_min_score_threshold(tree: list[CommentTreeNode], desired_size: int, low: int, high: int) -> int:
	mid = (low + high) // 2
	while get_tree_size(low, tree) < desired_size:
		low = low - max(mid - low, 5)
	while get_tree_size(high, tree) > desired_size:
		high = high + max(high - mid, 5)

	while low <= high:
		mid = (low + high) // 2
		size = get_tree_size(mid, tree)
		if size == desired_size:
			return mid
		elif size < desired_size:
			high = mid - 1
		else:
			low = mid + 1
	return low


def get_cropped_tree(tree: list[CommentTreeNode], min_score_threshold: int | None) -> list[CommentTreeNode]:
	items: list[CommentTreeNode] = []
	for node in tree:
		if min_score_threshold is not None and node.score < min_score_threshold:
			continue
		items.append(
		    CommentTreeNode(
		        author=node.author,
		        text=node.text,
		        content_id=node.content_id,
		        score=node.score,
		        replies=get_cropped_tree(node.replies, min_score_threshold),
		    ))
	return items


def get_comment_tree(submission: Submission, max_size: int) -> SubmissionTreeNode:
	comment_tree = get_comment_tree_recursive(submission.comments)
	tree_size = get_tree_size(None, comment_tree)
	if tree_size >= max_size:
		min_score_threshold = find_min_score_threshold(comment_tree, max_size, 1, 500)
	else:
		min_score_threshold = None
	cropped_tree = get_cropped_tree(comment_tree, min_score_threshold)
	return SubmissionTreeNode(
	    subreddit=submission.subreddit.display_name,
	    content_id=SUBMISSION_PREFIX + submission.id,
	    author=get_author_name(submission),
	    title=submission.title,
	    text=submission.selftext,
	    replies=cropped_tree,
	)


def canonicalize_subreddit_name(subreddit_name: str) -> str:
	subreddit = subreddit_name.strip().lower()
	if subreddit.startswith('r/'):
		subreddit = subreddit[2:]
	return subreddit
