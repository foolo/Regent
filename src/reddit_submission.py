from pydantic import BaseModel


class RedditSubmission(BaseModel):
	title: str
	selftext: str
