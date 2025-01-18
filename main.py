import argparse
from enum import Enum
import logging
import os
import sys
import yaml
from praw import Reddit  # type: ignore

from src.agent_env import AgentEnv
from src.log_config import logger
from src.agent import run_agent
from src.reddit_utils import LoadConfigException, load_reddit_config
from src.pydantic_models.agent_config import AgentConfig
from src.providers.openai_provider import OpenAIProvider
from src.pydantic_models.openai_config import OpenAIConfig


def initialize_reddit():
	try:
		config = load_reddit_config()
	except LoadConfigException as e:
		logger.error(e)
		sys.exit(1)
	reddit = Reddit(
	    client_id=config.client_id,
	    client_secret=config.client_secret,
	    user_agent=config.user_agent,
	    refresh_token=config.refresh_token,
	)
	logger.info(f"Logged in as: {reddit.user.me()}")
	return reddit


def load_config(path: str):
	if os.path.exists(path):
		with open(path) as f:
			return yaml.safe_load(f)
	else:
		raise FileNotFoundError(f"File {path} not found. Create it by copying {path}.example to {path} and edit the values.")


def run():
	parser = argparse.ArgumentParser()
	parser.add_argument("agent_schema", type=argparse.FileType('r'))
	parser.add_argument("provider", type=str)
	parser.add_argument("--confirm", action="store_true", help="Enables confirmation before each action.")
	parser.add_argument("--test_mode", action="store_true", help="Run the agent in test mode. Inbox comments are not marked as read.")
	parser.add_argument("--iteration_interval", type=int, default=60, help="The interval in seconds between agent iterations.")
	parser.add_argument("--log_level", type=str, default="INFO", help="Set the log level. Default: INFO")
	args = parser.parse_args()

	log_level = logging.getLevelNamesMapping().get(args.log_level)
	if log_level is None:
		raise ValueError(f"Invalid log level: {args.log_level}")
	logger.setLevel(log_level)

	reddit = initialize_reddit()

	Providers = Enum('KnownProviders', ['openai'])
	if args.provider not in [provider.name for provider in Providers]:
		raise ValueError(f"Unknown provider: {args.provider}. Available providers: {', '.join([provider.name for provider in Providers])}")
	provider_enum = Providers[args.provider]
	logger.info(f'Using provider: {provider_enum.name}')

	if provider_enum.name == Providers.openai.name:
		config_obj = load_config('config/openai_config.yaml')
		config = OpenAIConfig(**config_obj)
		provider = OpenAIProvider(config)
	else:
		raise ValueError(f"Provider not implemented: {provider_enum.name}")

	agent_schema = args.agent_schema
	agent_schema_obj = yaml.safe_load(agent_schema)

	agent_config = AgentConfig(**agent_schema_obj)
	logger.info(f'Loaded agent: {agent_config.name}')

	confirm: bool = args.confirm
	test_mode: bool = args.test_mode
	iteration_interval: int = args.iteration_interval
	agent_state_filename = 'agent_state.json'
	agent_env = AgentEnv(agent_state_filename, agent_config, provider, reddit, confirm, test_mode, iteration_interval)
	run_agent(agent_env)


if __name__ == '__main__':
	run()
