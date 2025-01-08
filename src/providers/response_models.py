from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class RedditSubmission(BaseModel):
	title: str
	selftext: str


class RedditReply(BaseModel):
	reply_needed: bool
	body: Optional[str]


class ShowInboxCommand(BaseModel):
	literal: Literal["show_inbox"]


class ShowConversationForCommentCommand(BaseModel):
	literal: Literal["show_conversation_for_comment"]
	comment_id: str


class ShowUsernameCommand(BaseModel):
	literal: Literal["show_username"]


class MarkCommentAsReadCommand(BaseModel):
	literal: Literal["mark_comment_as_read"]
	comment_id: str


class ReplyToCommentCommand(BaseModel):
	literal: Literal["reply_to_comment"]
	comment_id: str
	reply: str

	def __str__(self):
		return f"{self.literal} {self.comment_id} '{self.reply}'"


class CreateSubmissionCommand(BaseModel):
	literal: Literal["create_submission"]
	subreddit: str
	title: str
	selftext: str


class ActionDecision(BaseModel):
	motivation_behind_the_action: str
	command: ShowInboxCommand | ShowUsernameCommand | ReplyToCommentCommand | ShowConversationForCommentCommand | MarkCommentAsReadCommand | CreateSubmissionCommand

	def __str__(self):
		return f"{self.command} {self.motivation_behind_the_action}"
