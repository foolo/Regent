import json
import time
import praw
import praw.models
from src.reddit_utils import get_comment_chain
import praw.models
from src.providers.base_provider import BaseProvider
from src.pydantic_models.agent_info import AgentInfo


def run_agent(agent_info: AgentInfo, provider: BaseProvider, reddit: praw.Reddit):
	while True:
		print('Commands:')
		print("  l=List posts, t=Generate a test submission without posting, i=Show inbox, c=Handle comment")
		print("Enter command:")
		command = input()
		if command == "c":
			current_user = reddit.user.me()
			if not current_user:
				print("No user logged in")
				continue
			username = current_user.name
			for item in reddit.inbox.unread(limit=None):
				if isinstance(item, praw.models.Comment):
					current_utc = int(time.time())
					if current_utc - item.created_utc > 600:
						print(f"Handle comment from: {item.author}, Comment: {item.body}")
						root_submission, comments = get_comment_chain(item, reddit)
						print(f"- Root submission: {root_submission}, Author: {root_submission.author}, Title: {root_submission.title}, Text: {root_submission.selftext}")
						for comment in comments:
							print(f"- Comment: {comment}, Author: {comment.author}, Text: {comment.body}")
						conversation_struct = {}
						conversation_struct['root_post'] = {'author': root_submission.author.name, 'title': root_submission.title, 'text': root_submission.selftext}
						conversation_struct['comments'] = [{'author': comment.author.name, 'text': comment.body} for comment in comments]

						system_prompt = agent_info.agent_description + "\n\n"
						system_prompt += "You are in a conversation on Reddit. The conversation is a chain of comments on the subreddit r/" + root_submission.subreddit.display_name + ".\n"
						system_prompt += "Your username in the conversation is " + username + ".\n"
						system_prompt += "Your task is to first determine whether the last comment in the conversation requires a response."
						system_prompt += "Some examples of comments that require a response are questions, requests for clarification, or comments that are open-ended.\n"
						system_prompt += "Some examples of comments that do not require a response are comments that are acknowledgements and agreements.\n"
						system_prompt += "If a response is needed, set the 'reply_needed' field to true and provide a response in the 'body' field. Otherwise set the 'reply_needed' field to false and leave the 'body' field undefined.\n"
						system_prompt += "The response, if reeded, should be thoughtful and engaging and at most 500 characters long.\n"
						prompt = "The conversation is as follows: \n" + json.dumps(conversation_struct, indent=1)
						print("System Prompt:")
						print(system_prompt)
						print("Prompt:")
						print(prompt)
						response = provider.generate_comment(system_prompt, prompt)
						if response is None:
							print("Failed to generate a response")
							continue
						print("Response:")
						print(response)
						if response.reply_needed:
							if not response.body or response.body == "":
								print("Warning: Response needed but no body provided")
								continue
							if input("Post response? (y/n): ") == "y":
								print("Posting...")
								comments[-1].reply(response.body)
								print("Posted!")
						break
		elif command == "i":
			print("Inbox:")
			for item in reddit.inbox.unread(limit=None):  # type: ignore
				if isinstance(item, praw.models.Comment):
					print(f"Comment from: {item.author}, Comment: {item.body}")
				elif isinstance(item, praw.models.Message):
					print(f"Message from: {item.author}, Subject: {item.subject}, Message: {item.body}")
		elif command == "l":
			print(f'Listing posts from subreddit: {agent_info.active_subreddit}')
			for submission in reddit.subreddit(agent_info.active_subreddit).new(limit=10):
				print(submission.title)
		elif command == "t":
			prompt = "Generate an engaging reddit submission. Use at most 500 characters. Avoid emojis and hashtags."
			system_prompt = agent_info.agent_description
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
