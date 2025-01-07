# generated by datamodel-codegen:
#   filename:  agent_info_schema.json

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ActiveOnSubreddit(BaseModel):
    name: str = Field(..., description='The name of the subreddit')
    post_instructions: Optional[str] = Field(
        None,
        description='Instructions for the agent on how to make posts to the subreddit',
    )


class Behavior(BaseModel):
    comment_reply_needed_classification: str = Field(
        ...,
        description='Explain what kinds of comments the agent should reply to, and what kinds it should ignore.',
    )
    post_reply_needed_classification: str = Field(
        ...,
        description='Explain what kinds of posts the agent should reply to, and what kinds it should ignore.',
    )
    reply_style: str = Field(..., description="The style of the agent's replies.")
    post_style: str = Field(..., description="The style of the agent's posts.")
    reply_delay_minutes: int = Field(
        ...,
        description='The minimum time in minutes before the agent will reply to a comment.',
    )
    minimum_time_between_posts_hours: int = Field(
        ...,
        description="The minimum time since the agent's last posts in hours before it will make another post.",
    )


class AgentInfo(BaseModel):
    name: str = Field(..., description='The name of the agent')
    agent_description: str = Field(..., description='A description of the agent')
    active_on_subreddits: List[ActiveOnSubreddit] = Field(
        ..., description='The subreddits the agent is active on', min_length=1
    )
    behavior: Behavior = Field(..., description='The behavior of the agent')
