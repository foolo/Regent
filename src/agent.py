import praw  # type: ignore
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_info import AgentInfo


def run_agent(agent_info: AgentInfo, provider: BaseProvider, reddit: praw.Reddit):
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
