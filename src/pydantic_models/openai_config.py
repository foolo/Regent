from pydantic import BaseModel, Field


class OpenAIConfig(BaseModel):
	api_key: str = Field(..., description='The API key for the OpenAI API')
	model_id: str = Field(..., description='The ID of the OpenAI model to use')
