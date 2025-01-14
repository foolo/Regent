from typing import Literal
from pydantic import BaseModel


class ShowUsername(BaseModel):
	literal: Literal["show_username"]


class ShowNewPost(BaseModel):
	literal: Literal["show_new_post"]


class ShowConversationWithNewActivity(BaseModel):
	literal: Literal["show_conversation_with_new_activity"]


class ReplyToContent(BaseModel):
	literal: Literal["reply_to_content"]
	content_id: str
	reply_text: str


class CreatePost(BaseModel):
	literal: Literal["create_post"]
	subreddit: str
	post_title: str
	post_text: str


class Action(BaseModel):
	motivation_behind_the_action: str
	command: ShowUsername | ShowNewPost | ReplyToContent | ShowConversationWithNewActivity | CreatePost
