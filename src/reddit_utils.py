import praw
import praw.models

comment_prefix = 't1_'
submission_prefix = 't3_'


def get_comment_chain(comment: praw.models.Comment, reddit: praw.Reddit) -> tuple[praw.models.Submission, list[praw.models.Comment]]:
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
