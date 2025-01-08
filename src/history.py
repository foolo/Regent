from dataclasses import dataclass, field


@dataclass
class HistoryTurn:
	model_action: str
	action_result: str


@dataclass
class History:
	turns: list[HistoryTurn] = field(default_factory=list)
