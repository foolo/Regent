from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel, Field


class HistoryItem(BaseModel):
	notes_and_strategy: str = Field(..., description='Notes and strategy for a specific action')


class StreamedSubmission(BaseModel):
	id: str = Field(..., description='The id of the submission')
	timestamp: datetime = Field(..., description='The timestamp of the submission')


class AgentState(BaseModel):
	history: List[HistoryItem] = Field(
	    description='Action and result history of the agent',
	    default=[],
	)
	streamed_submissions: List[StreamedSubmission] = Field(
	    description='The submissions that have been streamed to the state',
	    default=[],
	)
	streamed_submissions_until_timestamp: datetime = Field(
	    description='The timestamp until which submissions have been streamed to the agent state',
	    default=datetime.fromtimestamp(0, timezone.utc),
	)
