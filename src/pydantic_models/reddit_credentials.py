# generated by datamodel-codegen:
#   filename:  reddit_credentials_schema.json

from __future__ import annotations

from pydantic import BaseModel, Field


class RedditCredentials(BaseModel):
    client_id: str = Field(..., description='The client id of the reddit app')
    client_secret: str = Field(..., description='The client secret of the reddit app')
    username: str = Field(..., description='The username of the reddit account')
