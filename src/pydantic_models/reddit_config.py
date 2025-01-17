from typing import Optional
from pydantic import BaseModel, Field


class RedditConfig(BaseModel):
	client_id: str = Field(..., description='The client id of the Reddit app')
	client_secret: str = Field(..., description='The client secret of the Reddit app')
	refresh_token: Optional[str] = Field(None, description='The refresh token of the Reddit app')
	user_agent: Optional[str] = Field(None, description='The user agent of the Reddit app')
