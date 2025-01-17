from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class HistoryItem(BaseModel):
	model_action: str = Field(..., description='The action taken by the model')
	action_result: str = Field(..., description='The result of the action')


class StreamedSubmission(BaseModel):
	id: str = Field(..., description='The id of the submission')
	timestamp: datetime = Field(..., description='The timestamp of the submission')


class AgentState(BaseModel):
	history: List[HistoryItem] = Field(..., description='Action and result history of the agent')
	streamed_submissions: List[StreamedSubmission] = Field(..., description='The submissions that have been streamed to the state')
	streamed_submissions_until_timestamp: datetime = Field(..., description='The timestamp until which submissions have been streamed to the agent state')
