### Prerequisites

```
pip install praw
pip install datamodel-code-generator
pip install pyyaml

pip install openai   #if using OpenAI model
```

### Usage

Running with the example agent

```
python3 main.py config/example_agent.yaml
```

### Generate models

Needed when the corresponding schema in `schemas/` has been modified

```
datamodel-codegen --input schemas/reddit_config_schema.json --input-file-type=jsonschema --output src/pydantic_models/reddit_config.py --output-model-type=pydantic_v2.BaseModel --disable-timestamp
datamodel-codegen --input schemas/openai_config_schema.json --input-file-type=jsonschema --output src/pydantic_models/openai_config.py --output-model-type=pydantic_v2.BaseModel --disable-timestamp
datamodel-codegen --input schemas/agent_info_schema.json --input-file-type=jsonschema --output src/pydantic_models/agent_info.py --output-model-type=pydantic_v2.BaseModel --disable-timestamp
```
