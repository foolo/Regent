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
	pass


class ShowUsernameCommand(BaseModel):
	literal: Literal["show_username"]
	pass


class ReplyToCommentCommand(BaseModel):
	literal: Literal["reply_to_comment"]
	comment_id: str
	reply: str

	def __str__(self):
		return f"{self.literal} {self.comment_id} '{self.reply}'"


class ActionDecision(BaseModel):
	motivation_behind_the_action: str
	command: ShowInboxCommand | ShowUsernameCommand | ReplyToCommentCommand

	def __str__(self):
		return f"{self.command} {self.motivation_behind_the_action}"
