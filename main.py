import argparse
from enum import Enum
import os
import sys
import praw  # type: ignore
import yaml

from src.reddit_config_loader import load_reddit_config
from src.pydantic_models.agent_info import AgentInfo
from src.providers.openai_provider import OpenAIProvider
from src.pydantic_models.openai_config import OpenAIConfig


def initialize_reddit():
	config = load_reddit_config()
	if not config.refresh_token or config.refresh_token == "":
		print("No reddit refresh token found. Run 'python reddit_auth.py' to generate one.")
		sys.exit(0)
	reddit = praw.Reddit(
	    client_id=config.client_id,
	    client_secret=config.client_secret,
	    user_agent=config.user_agent,
	    refresh_token=config.refresh_token,
	    username=config.username,
	)
	print(f"Logged in as: {reddit.user.me()}")
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
		raise ValueError(f"Unknown provider: {args.provider}. Available providers: {', '.join([provider.name for provider in Providers])}")
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
		elif command == "t":
			prompt = "Generate an engaging reddit submission. Use at most 500 characters. Avoid emojis and hashtags."
			system_prompt = agent_info.bio
			response = provider.generate_submission(system_prompt, prompt)
			if response is None:
				print("Failed to generate a response")
				continue
			print("Response:")
			print(response)
			if input(f"Post submission to {agent_info.active_subreddit}? (y/n): ") == "y":
				print("Posting...")
				reddit.subreddit(agent_info.active_subreddit).submit(response.title, selftext=response.selftext)
				print("Posted!")
		else:
			print(f"Invalid command: '{command}'")


if __name__ == '__main__':
	run()
