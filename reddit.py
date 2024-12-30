import argparse
import os
import praw  # type: ignore
import yaml
from agent_info_model import AgentInfo
from reddit_credentials_model import RedditCredentials

reddit_credentials_filename = 'config/reddit_credentials.yaml'

if os.path.exists(reddit_credentials_filename):
    with open(reddit_credentials_filename) as f:
        credentials_obj = yaml.safe_load(f)
else:
    raise FileNotFoundError(
        f"File {reddit_credentials_filename} not found. Create it by copying reddit_credentials.yaml.example to reddit_credentials.yaml and filling in the values."
    )

credentials = RedditCredentials(**credentials_obj)

reddit = praw.Reddit(
    client_id=credentials.client_id,
    client_secret=credentials.client_secret,
    user_agent="RedditAiBot, " + credentials.username,
    username=credentials.username,
)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("agent_schema", type=argparse.FileType('r'))
    args = parser.parse_args()
    agent_schema = args.agent_schema
    agent_schema_obj = yaml.safe_load(agent_schema)

    agent_info = AgentInfo(**agent_schema_obj)

    print(f'Loaded agent: {agent_info.name}')

    while True:
        print('Commands:')
        print("  l=List posts")
        print("Enter command:")
        command = input()
        if command == "l":
            print(
                f'Listing posts from subreddit: {agent_info.active_subreddit}')
            for submission in reddit.subreddit(
                    agent_info.active_subreddit).new(limit=10):
                print(submission.title)
        else:
            print("Invalid command")


if __name__ == '__main__':
    run()
