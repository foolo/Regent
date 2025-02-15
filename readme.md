# Regent - Reddit AI Agent

Regent is a tool for running your own AI agent on Reddit.

## Installation and setup

### Install dependencies

```bash
pip install praw
pip install pyyaml
pip install colorama
pip install openai
```

### Create a Reddit application

Create a Reddit application on https://www.reddit.com/prefs/apps/

Select "web app" and set the redirect URI to `http://localhost:8080`

After the application is created, take note of:

- Client ID (the line just under "web app" in the upper left of the Reddit application)
- Client secret (the value to the right of "secret")

### Create a Reddit configuration file

Copy `config/reddit_config.yaml.example` to `config/reddit_config.yaml` and fill in the fields from the previous step, but leave `refresh_token` empty.

### Generate a Reddit refresh token

Make sure you are logged in to the Reddit account with which you want to run the agent.

Run `python reddit_auth.py` to generate a refresh token.
Add the refresh token to `reddit_config.yaml`.

**Details:** `reddit_auth.py` will start a local server at `http://localhost:8080`
and prompt you to visit Reddit's authorize URL to connect the application to your Reddit account.
When you have authorized the application, Reddit will redirect you to the local server.
The program will display the refresh token in the terminal.
You then need to manually add the refresh token to `reddit_config.yaml`.

### Customize the agent

Copy `agents/example_agent.yaml` to a new file, such as `agents/my_agent.yaml` and customize it as you like.
See the comments in the example file for more information.

## Usage

### Run the agent

```bash
python3 main.py agents/my_agent.yaml openai
```
