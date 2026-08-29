"""A2A (Agent-to-Agent) Protocol v1.0

Structured JSON protocol for communication between NEMESIS (main agent)
and its sub-agents. Supports task lifecycle, capability discovery,
progress streaming, error propagation, and heartbeat monitoring.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any, Literal


class A2AMessageType(str, Enum):
    """All message types in the A2A protocol."""
    CAPABILITY_QUERY = "capability_query"
    CAPABILITY_REPORT = "capability_report"
    TASK_ASSIGN = "task_assign"
    TASK_ACK = "task_ack"
    TASK_PROGRESS = "task_progress"
    TASK_REPORT = "task_report"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    ERROR = "error"
    CANCEL = "cancel"
    CANCEL_ACK = "cancel_ack"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class AgentCapability(str, Enum):
    """Capabilities an agent can declare."""
    READ_FILES = "read_files"
    WRITE_FILES = "write_files"
    EDIT_FILES = "edit_files"
    EXECUTE_BASH = "execute_bash"
    SEARCH_CODE = "search_code"
    LIST_DIRS = "list_dirs"
    WEB_SEARCH = "web_search"
    WEB_FETCH = "web_fetch"
    MCP_CALL = "mcp_call"
    FILE_OPS = "file_ops"
    PYTHON_DEV = "python_dev"
    SHELL_SCRIPTS = "shell_scripts"
    CODE_REVIEW = "code_review"
    DEBUGGING = "debugging"


@dataclass
class A2AEnvelope:
    """Every A2A message is wrapped in this envelope."""
    a2a_version: str = "1.0"
    type: A2AMessageType = A2AMessageType.ERROR
    sender: str = ""
    recipient: str = ""
    message_id: str = ""
    timestamp: float = 0.0
    in_reply_to: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = A2AMessageType(self.type)
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()

    def to_json(self) -> str:
        data = {
            "a2a_version": self.a2a_version,
            "type": self.type.value if isinstance(self.type, A2AMessageType) else self.type,
            "sender": self.sender,
            "recipient": self.recipient,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
        if self.in_reply_to:
            data["in_reply_to"] = self.in_reply_to
        return json.dumps(data, ensure_ascii=False, default=str)

    @classmethod
    def from_json(cls, raw: str) -> "A2AEnvelope":
        data = json.loads(raw) if isinstance(raw, str) else raw
        msg_type = data.get("type", "error")
        if isinstance(msg_type, str):
            msg_type = A2AMessageType(msg_type)
        return cls(
            a2a_version=data.get("a2a_version", "1.0"),
            type=msg_type,
            sender=data.get("sender", ""),
            recipient=data.get("recipient", ""),
            message_id=data.get("message_id", str(uuid.uuid4())),
            timestamp=float(data.get("timestamp") or time.time()),
            in_reply_to=data.get("in_reply_to"),
            payload=data.get("payload") or {},
        )

    @classmethod
    def create(
        cls,
        sender: str,
        recipient: str,
        msg_type: A2AMessageType,
        payload: Optional[Dict[str, Any]] = None,
        in_reply_to: Optional[str] = None,
    ) -> "A2AEnvelope":
        return cls(
            sender=sender,
            recipient=recipient,
            type=msg_type,
            payload=payload or {},
            in_reply_to=in_reply_to,
        )


@dataclass
class AgentManifest:
    """Self-declared capabilities and identity of an agent."""
    name: str
    version: str = "1.0"
    description: str = ""
    capabilities: List[AgentCapability] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    max_concurrent_tasks: int = 1
    max_tokens: int = 4096
    model: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": [c.value if isinstance(c, AgentCapability) else c for c in self.capabilities],
            "domains": self.domains,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "max_tokens": self.max_tokens,
            "model": self.model,
        }


@dataclass
class TaskArtifact:
    """An artifact produced by a task (file, log, etc.)."""
    path: str
    kind: Literal["file", "log", "data", "report"] = "file"
    description: str = ""


@dataclass
class TaskManifest:
    """Full specification of a task to delegate."""
    task_id: str = ""
    label: str = ""
    description: str = ""
    instructions: List[str] = field(default_factory=list)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_ms: int = 300000
    context_files: List[str] = field(default_factory=list)
    expected_output: str = ""
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.task_id:
            self.task_id = uuid.uuid4().hex[:12]
        if isinstance(self.priority, str):
            self.priority = TaskPriority(self.priority)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "label": self.label,
            "description": self.description,
            "instructions": self.instructions,
            "priority": self.priority.value if isinstance(self.priority, TaskPriority) else self.priority,
            "timeout_ms": self.timeout_ms,
            "context_files": self.context_files,
            "expected_output": self.expected_output,
            "tags": self.tags,
        }

    @classmethod
    def from_payload(cls, data: Dict[str, Any]) -> "TaskManifest":
        return cls(
            task_id=data.get("task_id", ""),
            label=data.get("label", ""),
            description=data.get("description", ""),
            instructions=data.get("instructions") or [],
            priority=data.get("priority", "normal"),
            timeout_ms=int(data.get("timeout_ms") or 300000),
            context_files=data.get("context_files") or [],
            expected_output=data.get("expected_output", ""),
            tags=data.get("tags") or [],
        )


@dataclass
class TaskReport:
    """Result report from a completed task."""
    task_id: str = ""
    status: TaskStatus = TaskStatus.COMPLETED
    summary: str = ""
    artifacts: List[TaskArtifact] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = TaskStatus(self.status)
            except ValueError:
                self.status = TaskStatus.COMPLETED

    def to_payload(self) -> Dict[str, Any]:
        arts = []
        for a in self.artifacts:
            if isinstance(a, TaskArtifact):
                arts.append({"path": a.path, "kind": a.kind, "description": a.description})
            elif isinstance(a, dict):
                arts.append(a)
            else:
                arts.append({"path": str(a), "kind": "file", "description": ""})
        return {
            "task_id": self.task_id,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "summary": self.summary,
            "artifacts": arts,
            "errors": self.errors,
            "stats": self.stats,
        }


class A2ACoordinator:
    """Coordinates A2A protocol on the main agent side."""

    def __init__(self, agent_name: str = "nemesis"):
        self.agent_name = agent_name
        self.known_agents: Dict[str, AgentManifest] = {}
        self.active_tasks: Dict[str, TaskManifest] = {}
        self.task_reports: Dict[str, TaskReport] = {}
        self._task_counter = 0

    def register_agent(self, manifest: AgentManifest) -> None:
        self.known_agents[manifest.name] = manifest

    def get_agent(self, name: str) -> Optional[AgentManifest]:
        return self.known_agents.get(name)

    def list_agents(self) -> List[AgentManifest]:
        return list(self.known_agents.values())

    def next_task_id(self) -> str:
        self._task_counter += 1
        return uuid.uuid4().hex[:12]

    def create_task_manifest(
        self,
        label: str,
        description: str,
        instructions: Optional[List[str]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_ms: int = 300000,
        context_files: Optional[List[str]] = None,
        expected_output: str = "",
        tags: Optional[List[str]] = None,
    ) -> TaskManifest:
        manifest = TaskManifest(
            task_id=self.next_task_id(),
            label=label,
            description=description,
            instructions=instructions or [description],
            priority=priority,
            timeout_ms=timeout_ms,
            context_files=context_files or [],
            expected_output=expected_output,
            tags=tags or [],
        )
        self.active_tasks[manifest.task_id] = manifest
        return manifest

    def get_task(self, task_id: str) -> Optional[TaskManifest]:
        return self.active_tasks.get(task_id)

    def complete_task(self, task_id: str, report: TaskReport) -> None:
        self.active_tasks.pop(task_id, None)
        if report is not None:
            self.task_reports[task_id] = report

    def build_capability_query(self, recipient: str) -> A2AEnvelope:
        return A2AEnvelope.create(self.agent_name, recipient, A2AMessageType.CAPABILITY_QUERY, {})

    def build_task_assign(self, recipient: str, manifest: TaskManifest) -> A2AEnvelope:
        return A2AEnvelope.create(
            self.agent_name, recipient, A2AMessageType.TASK_ASSIGN, manifest.to_payload()
        )

    def build_cancel(self, recipient: str, task_id: str, reason: str = "") -> A2AEnvelope:
        return A2AEnvelope.create(
            self.agent_name, recipient, A2AMessageType.CANCEL,
            {"task_id": task_id, "reason": reason},
        )

    def build_heartbeat(self, recipient: str) -> A2AEnvelope:
        return A2AEnvelope.create(self.agent_name, recipient, A2AMessageType.HEARTBEAT, {})

    def parse_envelope(self, raw: str) -> Optional[A2AEnvelope]:
        try:
            return A2AEnvelope.from_json(raw)
        except Exception:
            return None

    def parse_capability_report(self, envelope: A2AEnvelope) -> Optional[AgentManifest]:
        if envelope.type != A2AMessageType.CAPABILITY_REPORT:
            return None
        p = envelope.payload
        valid = {c.value for c in AgentCapability}
        caps = [AgentCapability(c) for c in p.get("capabilities", []) if c in valid]
        return AgentManifest(
            name=p.get("name", envelope.sender),
            version=p.get("version", "1.0"),
            description=p.get("description", ""),
            capabilities=caps,
            domains=p.get("domains") or [],
            max_concurrent_tasks=int(p.get("max_concurrent_tasks") or 1),
            max_tokens=int(p.get("max_tokens") or 4096),
            model=p.get("model", ""),
        )

    def parse_task_ack(self, envelope: A2AEnvelope) -> Optional[Dict[str, Any]]:
        if envelope.type != A2AMessageType.TASK_ACK:
            return None
        return envelope.payload

    def parse_task_progress(self, envelope: A2AEnvelope) -> Optional[Dict[str, Any]]:
        if envelope.type != A2AMessageType.TASK_PROGRESS:
            return None
        return envelope.payload

    def parse_task_report(self, envelope: A2AEnvelope) -> Optional[TaskReport]:
        if envelope.type != A2AMessageType.TASK_REPORT:
            return None
        p = envelope.payload
        artifacts = []
        for a in p.get("artifacts") or []:
            if isinstance(a, dict):
                artifacts.append(TaskArtifact(
                    path=a.get("path", ""),
                    kind=a.get("kind", "file"),
                    description=a.get("description", ""),
                ))
            elif isinstance(a, str):
                artifacts.append(TaskArtifact(path=a))
        try:
            status = TaskStatus(p.get("status", "completed"))
        except ValueError:
            status = TaskStatus.COMPLETED
        return TaskReport(
            task_id=p.get("task_id", ""),
            status=status,
            summary=p.get("summary", ""),
            artifacts=artifacts,
            errors=p.get("errors") or [],
            stats=p.get("stats") or {},
        )
