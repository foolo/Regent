from dataclasses import dataclass, field


@dataclass
class HistoryTurn:
	user_prompt: str
	response: str


@dataclass
class History:
	turns: list[HistoryTurn] = field(default_factory=list)
