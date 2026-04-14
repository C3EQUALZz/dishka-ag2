from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class SessionState:
    session_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ToolRequestState:
    tool_name: str
    request_id: UUID = field(default_factory=uuid4)
