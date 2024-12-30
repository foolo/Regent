import os
import praw  # type: ignore
import yaml
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
    for submission in reddit.subreddit("test").new(limit=10):
        print(submission.title)


if __name__ == '__main__':
    run()
