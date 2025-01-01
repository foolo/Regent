import argparse
from enum import Enum
import os
import sys
import praw  # type: ignore
import yaml

from src.reddit_auth import retrieve_refresh_token
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

	redirect_host = 'localhost'
	redirect_port = 8080

	config = RedditConfig(**config_obj)
	reddit = praw.Reddit(
	    client_id=config.client_id,
	    client_secret=config.client_secret,
	    user_agent="RedditAiBot, " + config.username,
	    redirect_uri=f"http://{redirect_host}:{redirect_port}",
	    refresh_token=config.refresh_token,
	    username=config.username,
	)

	if not config.refresh_token or config.refresh_token == "":
		print("No refresh token found. Starting the process to generate one...")
		retrieve_refresh_token(reddit, redirect_host, redirect_port)
		print(f"A refresh token has been generated. Add it in {config_filename} and restart the program.")
		sys.exit(0)

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
