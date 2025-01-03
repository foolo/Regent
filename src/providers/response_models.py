from typing import Optional
from pydantic import BaseModel


class RedditSubmission(BaseModel):
	title: str
	selftext: str


class RedditCommentReply(BaseModel):
	reply_needed: bool
	body: Optional[str]
