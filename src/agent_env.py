from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from praw import Reddit  # type: ignore
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_state import AgentState
from src.pydantic_models.agent_config import AgentConfig


@dataclass
class AgentEnv:
	state_filename: str
	agent_config: AgentConfig
	provider: BaseProvider
	reddit: Reddit
	test_mode: bool
	iteration_interval: int
	state: AgentState = field(init=False)

	def __post_init__(self):
		if os.path.exists(self.state_filename):
			with open(self.state_filename) as f:
				whole_file_as_string = f.read()
				self.state = AgentState.model_validate_json(whole_file_as_string)
		else:
			self.state = AgentState(history=[], streamed_submissions=[], streamed_submissions_until_timestamp=datetime.fromtimestamp(0, timezone.utc))

	def save_state(self):
		with open(self.state_filename, 'w') as f:
			f.write(self.state.model_dump_json(indent=2))
