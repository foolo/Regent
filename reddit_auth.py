#!/usr/bin/env python

import socket
import sys
import time
from praw import Reddit

from src.reddit_config_loader import REDDIT_CONFIG_FILENAME, load_reddit_config

# Modified from https://praw.readthedocs.io/en/stable/tutorials/refresh_token.html#obtaining-refresh-tokens

SCOPES = ["identity", "submit", "read", "privatemessages"]


def retrieve_refresh_token() -> int:
	config = load_reddit_config()
	redirect_host = 'localhost'
	redirect_port = 8080
	reddit = Reddit(
	    client_id=config.client_id,
	    client_secret=config.client_secret,
	    user_agent=config.user_agent,
	    redirect_uri=f"http://{redirect_host}:{redirect_port}",
	)

	state = str(time.time())
	url = reddit.auth.url(duration="permanent", scopes=SCOPES, state=state)
	print(f"To connect your Reddit account to this application, open the following URL in your browser:")
	print(url)

	client = receive_connection(redirect_host, redirect_port)
	data = client.recv(1024).decode("utf-8")
	param_tokens = data.split(" ", 2)[1].split("?", 1)[1].split("&")
	params = {key: value for (key, value) in [token.split("=") for token in param_tokens]}

	if state != params["state"]:
		send_message(
		    client,
		    f"State mismatch. Expected: {state} Received: {params['state']}",
		)
		return 1
	elif "error" in params:
		send_message(client, params["error"])
		return 1

	refresh_token = reddit.auth.authorize(params["code"])
	send_message(client, f"Refresh token: {refresh_token}")
	print(f"A refresh token has been generated. Add it in {REDDIT_CONFIG_FILENAME} and start the application.")
	return 0


def receive_connection(redirect_host: str, redirect_port: int) -> socket.socket:
	"""Wait for and then return a connected socket..

    Opens a TCP connection, and waits for a single client.

    """
	server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server.bind((redirect_host, redirect_port))
	server.listen(1)
	client = server.accept()[0]
	server.close()
	return client


def send_message(client: socket.socket, message: str):
	"""Send message to client and close the connection."""
	print(message)
	client.send(f"HTTP/1.1 200 OK\r\n\r\n{message}".encode("utf-8"))
	client.close()


if __name__ == "__main__":
	sys.exit(retrieve_refresh_token())
