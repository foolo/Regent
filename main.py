import argparse
from enum import Enum
import os
import praw  # type: ignore
import yaml

from src.pydantic_models.agent_info import AgentInfo
from src.pydantic_models.reddit_credentials import RedditCredentials
from src.providers.openai_provider import OpenAIProvider
from src.pydantic_models.openai_credentials import OpenAICredentials

reddit_credentials_filename = 'config/reddit_credentials.yaml'

if os.path.exists(reddit_credentials_filename):
	with open(reddit_credentials_filename) as f:
		credentials_obj = yaml.safe_load(f)
else:
	raise FileNotFoundError(
	    f"File {reddit_credentials_filename} not found. Create it by copying reddit_credentials.yaml.example to reddit_credentials.yaml and filling in the values.")

credentials = RedditCredentials(**credentials_obj)

reddit = praw.Reddit(
    client_id=credentials.client_id,
    client_secret=credentials.client_secret,
    user_agent="RedditAiBot, " + credentials.username,
    username=credentials.username,
)

KnownProviders = Enum('KnownProviders', ['openai'])


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

	if args.provider not in [provider.name for provider in KnownProviders]:
		raise ValueError(f"Unknown provider: {args.provider}")
	provider_enum = KnownProviders[args.provider]
	print(f'Using provider: {provider_enum.name}')

	if provider_enum.name == KnownProviders.openai.name:
		credentials_obj = load_config('config/openai_credentials.yaml')
		credentials = OpenAICredentials(**credentials_obj)
		provider = OpenAIProvider(credentials)
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
