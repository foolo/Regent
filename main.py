import argparse
from enum import Enum
import logging
import os
import sys
import yaml
from praw import Reddit

from src.agent import run_agent
from src.reddit_config_loader import load_reddit_config
from src.pydantic_models.agent_info import AgentInfo
from src.providers.openai_provider import OpenAIProvider
from src.pydantic_models.openai_config import OpenAIConfig

logger = logging.getLogger(__name__)


def initialize_reddit():
	config = load_reddit_config()
	if not config.refresh_token or config.refresh_token == "":
		logger.warning("No Reddit refresh token found. Run 'python reddit_auth.py' to generate one.")
		sys.exit(0)
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
	logging.basicConfig(
	    level=logging.INFO,
	    style='{',
	    format='{levelname:8} {message}',
	    datefmt='%Y-%m-%d %H:%M:%S',
	)
	parser = argparse.ArgumentParser()
	parser.add_argument("agent_schema", type=argparse.FileType('r'))
	parser.add_argument("provider", type=str)
	parser.add_argument("--interactive", action="store_true", help="Run the agent in interactive mode, allowing you to confirm before posting.")
	parser.add_argument("--iteration_interval", type=int, default=60, help="The interval in seconds between agent iterations.")
	args = parser.parse_args()

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

	agent_info = AgentInfo(**agent_schema_obj)
	logger.info(f'Loaded agent: {agent_info.name}')

	interactive: bool = args.interactive
	iteration_interval: int = args.iteration_interval
	run_agent(agent_info, provider, reddit, interactive, iteration_interval)


if __name__ == '__main__':
	run()
