### Prerequisites

```
pip install praw
pip install datamodel-code-generator
pip install pyyaml

pip install openai   #if using OpenAI model
```

### Usage

#### Create a Reddit application

While logged into the Reddit account with which you want to run the agent,
create a Reddit application on https://www.reddit.com/prefs/apps/

Select "web app" and set the redirect URI to `http://localhost:8080`

After the application is created, take note of:

- Client ID - the line just under "web app" in the upper left of the Reddit application
- Client secret - the value to the right of "secret"

#### Running with the example agent

```
python3 main.py agents/example_agent.yaml openai
```

The first time you run the program, it needs to be paired with your Reddit account.
The program will detect if the `refresh_token` field is missing in `reddit_config.yaml`.
If it is, it will start a local server at `http://localhost:8080`
and prompt you to visit Reddit's authorize URL to connect the application to your Reddit account.
After you authorize the application, Reddit will redirect you to the local server.
The program will display the refresh token in the terminal.
You then need to manually add the refresh token to `reddit_config.yaml`, and start the program again.

### Generate models

Needed when the corresponding schema in `schemas/` has been modified

```
datamodel-codegen --input schemas/reddit_config_schema.json --input-file-type=jsonschema --output src/pydantic_models/reddit_config.py --output-model-type=pydantic_v2.BaseModel --disable-timestamp
datamodel-codegen --input schemas/openai_config_schema.json --input-file-type=jsonschema --output src/pydantic_models/openai_config.py --output-model-type=pydantic_v2.BaseModel --disable-timestamp
datamodel-codegen --input schemas/agent_info_schema.json --input-file-type=jsonschema --output src/pydantic_models/agent_info.py --output-model-type=pydantic_v2.BaseModel --disable-timestamp
```
