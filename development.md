## Prerequisites

In addition to the prerequisites listed in readme.md, you need the following to work with the codebase:

```bash
pip install datamodel-code-generator
```

## Generate models

Needed when the corresponding schema in `schemas/` has been modified

```bash
datamodel-codegen --input schemas/reddit_config_schema.json --input-file-type=jsonschema --output src/pydantic_models/reddit_config.py --output-model-type=pydantic_v2.BaseModel --disable-timestamp
datamodel-codegen --input schemas/openai_config_schema.json --input-file-type=jsonschema --output src/pydantic_models/openai_config.py --output-model-type=pydantic_v2.BaseModel --disable-timestamp
datamodel-codegen --input schemas/agent_info_schema.json --input-file-type=jsonschema --output src/pydantic_models/agent_info.py --output-model-type=pydantic_v2.BaseModel --disable-timestamp
```
