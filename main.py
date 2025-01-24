import argparse
from datetime import datetime
from enum import Enum
import logging
import os
import sys
import yaml
from praw import Reddit  # type: ignore

from src.agent_env import AgentEnv
from src.formatted_logger import ColoredTerminalLogger, MarkdownLogger, fmtlog
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
	fmtlog.text(f"Logged in as: {reddit.user.me()}")
	return reddit


def load_config(path: str):
	if os.path.exists(path):
		with open(path) as f:
			return yaml.safe_load(f)
	else:
		raise FileNotFoundError(f"File {path} not found. Create it by copying {path}.example to {path} and edit the values.")


def run():
	Providers = Enum('KnownProviders', ['openai'])
	available_providers = [provider.name for provider in Providers]
	parser = argparse.ArgumentParser()
	parser.add_argument("agent_schema_file", type=str, help="Path to the agent schema file.")
	parser.add_argument("provider", type=str, help=f"AI provider to use. Available providers: {', '.join(available_providers)}")
	parser.add_argument("--test_mode", action="store_true", help="Enable confirmation before each action or step. Create post will always be available.")
	parser.add_argument("--log_level", type=str, default="INFO", help="Set the log level. Default: INFO")
	parser.add_argument("--markdown_log_dir", type=str, help="Directory to save markdown logs (default: current working directory)", default=os.getcwd())
	args = parser.parse_args()
	assert isinstance(args.agent_schema_file, str)
	assert isinstance(args.provider, str)
	assert isinstance(args.test_mode, bool)
	assert isinstance(args.log_level, str)
	assert isinstance(args.markdown_log_dir, str)

	log_level = logging.getLevelNamesMapping().get(args.log_level)
	if log_level is None:
		raise ValueError(f"Invalid log level: {args.log_level}")
	logger.setLevel(log_level)

	markdown_log_filename = datetime.now().isoformat(sep="_", timespec="seconds") + ".log.md"
	fmtlog.register_logger(MarkdownLogger(os.path.join(args.markdown_log_dir, markdown_log_filename)))
	fmtlog.register_logger(ColoredTerminalLogger())

	reddit = initialize_reddit()

	if args.provider not in [provider.name for provider in Providers]:
		raise ValueError(f"Unknown provider: {args.provider}. Available providers: {', '.join(available_providers)}")
	provider_enum = Providers[args.provider]
	fmtlog.text(f'Using provider: {provider_enum.name}')

	if provider_enum.name == Providers.openai.name:
		config_obj = load_config('config/openai_config.yaml')
		config = OpenAIConfig(**config_obj)
		provider = OpenAIProvider(config)
	else:
		raise ValueError(f"Provider not implemented: {provider_enum.name}")

	with open(args.agent_schema_file) as f:
		agent_schema_obj = yaml.safe_load(f)

	agent_config = AgentConfig(**agent_schema_obj)
	fmtlog.text(f'Loaded agent: {agent_config.name}')

	agent_state_filename = 'agent_state.json'
	agent_env = AgentEnv(agent_state_filename, agent_config, provider, reddit, args.test_mode)
	run_agent(agent_env)


if __name__ == '__main__':
	run()
