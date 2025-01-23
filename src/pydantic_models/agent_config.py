from typing import List
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
	name: str = Field(..., description='The name of the agent')
	agent_instructions: str = Field(..., description='A description of the agent')
	active_on_subreddits: List[str] = Field(..., description='The subreddits the agent is active on', min_length=1)
	max_post_age_for_replying_hours: int = Field(description='The maximum age of a post in hours that the agent will reply to.', default=24)
	minimum_time_between_posts_hours: int = Field(description="The minimum time since the agent's last posts in hours before it will make another post.", default=1)
	max_history_length: int = Field(description='Keep at most this many history items and remove the oldest items.', default=3)
	can_create_posts: bool = Field(description='Whether the agent is allowed to create posts.', default=True)
	can_reply_to_content: bool = Field(description='Whether the agent is allowed to reply to content.', default=True)
