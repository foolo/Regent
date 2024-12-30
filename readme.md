### Prerequisites

```
pip install praw
pip install datamodel-code-generator
pip install pyyaml
```

### Usage

Running with the example agent

```
python3 reddit.py config/example_agent.yaml
```

### Generate models

Needed when the corresponding schema in `schemas/` has been modified

```
datamodel-codegen --input schemas/reddit_credentials_schema.json --input-file-type=jsonschema --output src/pydantic_models/reddit_credentials.py --output-model-type=pydantic_v2.BaseModel
datamodel-codegen --input schemas/agent_info_schema.json --input-file-type=jsonschema --output src/pydantic_models/agent_info.py --output-model-type=pydantic_v2.BaseModel
```
