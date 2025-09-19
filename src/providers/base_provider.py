from abc import ABC, abstractmethod

from pydantic import BaseModel


class PostReplyData(BaseModel):
	content_id: str
	reply_text: str
	notes_and_strategy: str


class PostReply(BaseModel):
	data: PostReplyData | None = None


class InboxReplyData(BaseModel):
	reply_text: str
	notes_and_strategy: str


class InboxReply(BaseModel):
	data: InboxReplyData | None = None


class Submission(BaseModel):
	subreddit: str
	title: str
	text: str
	notes_and_strategy: str


class BaseProvider(ABC):
	@abstractmethod
	def reply_to_post(self, system_prompt: str) -> PostReply | None:
		pass

	@abstractmethod
	def reply_to_inbox(self, system_prompt: str) -> InboxReply | None:
		pass

	@abstractmethod
	def generate_submission(self, system_prompt: str) -> Submission | None:
		pass
