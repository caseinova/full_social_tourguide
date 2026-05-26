from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TaskState(str, Enum):
    IDLE = "idle"
    NAVIGATING = "navigating"
    EXPLORING = "exploring"
    TOURING = "touring"
    RECORDING = "recording"
    PAUSED = "paused"
    RECOVERING = "recovering"


@dataclass
class IntentToken:
    intent: str
    label: str = ""
    location: str = ""
    utterance: str = ""
    response: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        import json

        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, payload: str) -> "IntentToken":
        import json

        data = json.loads(payload)
        return cls(**data)


@dataclass
class Waypoint:
    x: float
    y: float
    yaw: float = 0.0
    note: str = ""


@dataclass
class Route:
    label: str
    waypoints: List[Waypoint] = field(default_factory=list)
    summary: str = ""


@dataclass
class DialogueMemory:
    active_route: str = ""
    current_stop_index: int = 0
    last_question: str = ""
    last_response: str = ""
    paused_task: Optional[TaskState] = None


@dataclass
class ControllerStatus:
    task_state: TaskState = TaskState.IDLE
    current_route: str = ""
    current_location: str = ""
    current_target: str = ""
    is_recording: bool = False
    is_paused: bool = False

    def to_json(self) -> str:
        import json

        payload = asdict(self)
        payload["task_state"] = self.task_state.value
        return json.dumps(payload)
