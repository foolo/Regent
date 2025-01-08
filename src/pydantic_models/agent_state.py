# generated by datamodel-codegen:
#   filename:  agent_state_schema.json

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class HistoryItem(BaseModel):
    model_action: str = Field(..., description='The action taken by the model')
    action_result: str = Field(..., description='The result of the action')


class AgentState(BaseModel):
    history: List[HistoryItem] = Field(
        ..., description='Action and result history of the agent'
    )
