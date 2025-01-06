# generated by datamodel-codegen:
#   filename:  agent_info_schema.json

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class Behavior(BaseModel):
    reply_needed_classification: str = Field(
        ...,
        description='Explain what kinds of comments the agent should reply to, and what kinds it should ignore.',
    )
    reply_style: str = Field(..., description="The style of the agent's replies.")
    submission_style: str = Field(
        ..., description="The style of the agent's submissions."
    )
    minimum_comment_age_minutes: int = Field(
        ...,
        description='The minimum age of a comment in minutes before the agent will reply to it.',
    )
    minimum_time_between_submissions_hours: int = Field(
        ...,
        description="The minimum time since the agent's last submission in hours before it will make another submission.",
    )


class AgentInfo(BaseModel):
    name: str = Field(..., description='The name of the agent')
    agent_description: str = Field(..., description='A description of the agent')
    active_on_subreddits: List[str] = Field(
        ..., description='The subreddits the agent is active on', min_length=1
    )
    behavior: Behavior = Field(..., description='The behavior of the agent')
