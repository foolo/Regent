import os
import yaml
from src.pydantic_models.reddit_config import RedditConfig

REDDIT_CONFIG_FILENAME = 'config/reddit_config.yaml'


def load_reddit_config():
	if os.path.exists(REDDIT_CONFIG_FILENAME):
		with open(REDDIT_CONFIG_FILENAME) as f:
			config_obj = yaml.safe_load(f)
	else:
		raise FileNotFoundError(
		    f"File {REDDIT_CONFIG_FILENAME} not found. Create it by copying {REDDIT_CONFIG_FILENAME}.example to {REDDIT_CONFIG_FILENAME} and filling in the values.")
	config = RedditConfig(**config_obj)
	if not config.user_agent or config.user_agent == "":
		config.user_agent = f"RedditAiAgent"
	return config
