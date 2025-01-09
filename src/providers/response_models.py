from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class RedditSubmission(BaseModel):
	title: str
	selftext: str


class RedditReply(BaseModel):
	reply_needed: bool
	body: Optional[str]


class ShowUsername(BaseModel):
	literal: Literal["show_username"]


class ShowNewPost(BaseModel):
	literal: Literal["show_new_post"]


class ShowConversationWithNewActivity(BaseModel):
	literal: Literal["show_conversation_with_new_activity"]


class ReplyToComment(BaseModel):
	literal: Literal["reply_to_comment"]
	comment_id: str
	reply_text: str

	def __str__(self):
		return f"{self.literal} {self.comment_id} '{self.reply_text}'"


class CreatePost(BaseModel):
	literal: Literal["create_post"]
	subreddit: str
	post_title: str
	post_text: str


class Action(BaseModel):
	motivation_behind_the_action: str
	command: ShowUsername | ShowNewPost | ReplyToComment | ShowConversationWithNewActivity | CreatePost

	def __str__(self):
		return f"{self.command} {self.motivation_behind_the_action}"
