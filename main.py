import argparse
from enum import Enum
import os
import praw  # type: ignore
import yaml

from src.pydantic_models.agent_info import AgentInfo
from src.pydantic_models.reddit_config import RedditConfig
from src.providers.openai_provider import OpenAIProvider
from src.pydantic_models.openai_config import OpenAIConfig


def initialize_reddit():
	config_filename = 'config/reddit_config.yaml'

	if os.path.exists(config_filename):
		with open(config_filename) as f:
			config_obj = yaml.safe_load(f)
	else:
		raise FileNotFoundError(f"File {config_filename} not found. Create it by copying {config_filename}.example to {config_filename} and filling in the values.")

	config = RedditConfig(**config_obj)
	reddit = praw.Reddit(
	    client_id=config.client_id,
	    client_secret=config.client_secret,
	    user_agent="RedditAiBot, " + config.username,
	    username=config.username,
	)
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
	args = parser.parse_args()

	reddit = initialize_reddit()

	Providers = Enum('KnownProviders', ['openai'])
	if args.provider not in [provider.name for provider in Providers]:
		raise ValueError(f"Unknown provider: {args.provider}")
	provider_enum = Providers[args.provider]
	print(f'Using provider: {provider_enum.name}')

	if provider_enum.name == Providers.openai.name:
		config_obj = load_config('config/openai_config.yaml')
		config = OpenAIConfig(**config_obj)
		provider = OpenAIProvider(config)
	else:
		raise ValueError(f"Provider not implemented: {provider_enum.name}")

	agent_schema = args.agent_schema
	agent_schema_obj = yaml.safe_load(agent_schema)

	agent_info = AgentInfo(**agent_schema_obj)

	print(f'Loaded agent: {agent_info.name}')

	while True:
		print('Commands:')
		print("  l=List posts, t=Generate a test submission without posting")
		print("Enter command:")
		command = input()
		if command == "l":
			print(f'Listing posts from subreddit: {agent_info.active_subreddit}')
			for submission in reddit.subreddit(agent_info.active_subreddit).new(limit=10):
				print(submission.title)
		if command == "t":
			prompt = "Generate an engaging reddit submission"
			system_prompt = agent_info.bio
			response = provider.generate_text(system_prompt, prompt)
			print("Response:")
			print(response)
		else:
			print("Invalid command")


if __name__ == '__main__':
	run()
