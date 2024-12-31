# generated by datamodel-codegen:
#   filename:  agent_info_schema.json

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    name: str = Field(..., description='The name of the agent')
    bio: str = Field(..., description='A short description of the agent')
    active_subreddit: str = Field(
        ..., description='The subreddit the agent is active in. Exclude the r/ prefix.'
    )
