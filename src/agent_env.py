from datetime import datetime, timezone
import os
from praw import Reddit  # type: ignore
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_state import AgentState
from src.pydantic_models.agent_config import AgentConfig


class AgentEnv:
	def __init__(self, state_filename: str, agent_config: AgentConfig, provider: BaseProvider, reddit: Reddit, confirm: bool, test_mode: bool, iteration_interval: int):
		if os.path.exists(state_filename):
			with open(state_filename) as f:
				whole_file_as_string = f.read()
				self.state = AgentState.model_validate_json(whole_file_as_string)
		else:
			self.state = AgentState(history=[], streamed_submissions=[], streamed_submissions_until_timestamp=datetime.fromtimestamp(0, timezone.utc))

		self.state_filename = state_filename
		self.agent_config = agent_config
		self.provider = provider
		self.reddit = reddit
		self.confirm = confirm
		self.test_mode = test_mode
		self.iteration_interval = iteration_interval

	def save_state(self):
		with open(self.state_filename, 'w') as f:
			f.write(self.state.model_dump_json(indent=2))
