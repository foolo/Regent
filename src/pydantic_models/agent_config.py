from typing import List
from pydantic import BaseModel, Field


class Behavior(BaseModel):
	max_post_age_for_replying_hours: int = Field(..., description='The maximum age of a post in hours that the agent will reply to.')
	minimum_time_between_posts_hours: int = Field(..., description="The minimum time since the agent's last posts in hours before it will make another post.")


class AgentConfig(BaseModel):
	name: str = Field(..., description='The name of the agent')
	agent_description: str = Field(..., description='A description of the agent')
	active_on_subreddits: List[str] = Field(..., description='The subreddits the agent is active on', min_length=1)
	behavior: Behavior = Field(..., description='The behavior of the agent')
