from typing import List
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
	name: str = Field(..., description='The name of the agent')
	agent_description: str = Field(..., description='A description of the agent')
	active_on_subreddits: List[str] = Field(..., description='The subreddits the agent is active on', min_length=1)
	max_post_age_for_replying_hours: int = Field(description='The maximum age of a post in hours that the agent will reply to.', default=24)
	minimum_time_between_posts_hours: int = Field(description="The minimum time since the agent's last posts in hours before it will make another post.", default=1)
