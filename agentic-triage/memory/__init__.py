"""Memory architecture — three-way split between ephemeral, persistent, and vault.

Per Nullresearch strategy:
- Ephemeral working memory: current task context, discarded after session
- Persistent agent memory: reusable preferences, skills, and procedures
- Vault: ground-truth source, read-only to agents

Agents remember how to work but re-read what is true when notes may have changed.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json
import hashlib
import uuid


@dataclass
class SessionContext:
    """Ephemeral working memory for a single agent session/task."""
    session_id: str
    task_id: str
    task_description: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context_variables: dict = field(default_factory=dict)
    conversation_history: list[dict] = field(default_factory=list)
    intermediate_results: dict = field(default_factory=dict)
    pending_actions: list[dict] = field(default_factory=list)
    is_active: bool = True

    def add_to_history(self, role: str, content: str):
        self.conversation_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "content": content,
        })

    def set_variable(self, key: str, value):
        self.context_variables[key] = value

    def get_variable(self, key: str, default=None):
        return self.context_variables.get(key, default)

    def close(self):
        self.is_active = False


@dataclass
class PersistentMemory:
    """Agent preferences, learned skills, and reusable procedures.

    Survives across sessions. Agents read/write here freely (within policy).
    Never contains vault-sourced facts — those are read fresh from the vault.
    """
    agent_id: str
    preferences: dict = field(default_factory=dict)
    learned_patterns: list[dict] = field(default_factory=list)
    workflow_templates: dict = field(default_factory=dict)
    evaluation_history: list[dict] = field(default_factory=list)
    version: int = 1


class MemoryManager:
    """Manages the three-way memory architecture.

    - Session memory: ephemeral, per-task, discarded on close
    - Persistent memory: agent-scoped, survives across sessions
    - Vault: external ground-truth source, read-only to agents
    """

    def __init__(self, storage_path: str = "data/memory_store"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._active_sessions: dict[str, SessionContext] = {}
        self._persistent_memories: dict[str, PersistentMemory] = {}
        self._vault_checksums: dict[str, str] = {}  # Track vault note freshness

    # --- Session Memory (Ephemeral) ---

    def create_session(self, task_id: str, task_description: str) -> SessionContext:
        """Create a new ephemeral session for a task."""
        session_id = str(uuid.uuid4())[:8]
        session = SessionContext(
            session_id=session_id,
            task_id=task_id,
            task_description=task_description,
        )
        self._active_sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Retrieve an active session."""
        return self._active_sessions.get(session_id)

    def close_session(self, session_id: str):
        """Close and discard ephemeral session context."""
        session = self._active_sessions.pop(session_id, None)
        if session:
            session.close()

    def resume_session(self, session_id: str, task_description: str) -> SessionContext:
        """Resume a previously paused session, restoring context.

        For long-running research tasks that persist across invocations.
        """
        session_file = self.storage_path / f"session_{session_id}.json"
        if session_file.exists():
            data = json.loads(session_file.read_text())
            session = SessionContext(
                session_id=session_id,
                task_id=data.get("task_id", ""),
                task_description=data.get("task_description", task_description),
                created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
                context_variables=data.get("context_variables", {}),
                conversation_history=data.get("conversation_history", []),
                intermediate_results=data.get("intermediate_results", {}),
                pending_actions=data.get("pending_actions", []),
            )
        else:
            session = self.create_session(task_id=str(uuid.uuid4())[:8], task_description=task_description)
            session.session_id = session_id

        self._active_sessions[session_id] = session
        return session

    def save_session_checkpoint(self, session_id: str):
        """Save session state to disk so it can be resumed later."""
        session = self._active_sessions.get(session_id)
        if not session:
            return
        session_file = self.storage_path / f"session_{session_id}.json"
        session_file.write_text(json.dumps({
            "session_id": session.session_id,
            "task_id": session.task_id,
            "task_description": session.task_description,
            "created_at": session.created_at,
            "context_variables": session.context_variables,
            "conversation_history": session.conversation_history,
            "intermediate_results": session.intermediate_results,
            "pending_actions": session.pending_actions,
        }, indent=2, default=str))

    # --- Persistent Memory ---

    def get_persistent_memory(self, agent_id: str = "default") -> PersistentMemory:
        """Load or create persistent memory for an agent."""
        if agent_id in self._persistent_memories:
            return self._persistent_memories[agent_id]

        mem_file = self.storage_path / f"persistent_{agent_id}.json"
        if mem_file.exists():
            data = json.loads(mem_file.read_text())
            memory = PersistentMemory(
                agent_id=agent_id,
                preferences=data.get("preferences", {}),
                learned_patterns=data.get("learned_patterns", []),
                workflow_templates=data.get("workflow_templates", {}),
                evaluation_history=data.get("evaluation_history", []),
                version=data.get("version", 1),
            )
        else:
            memory = PersistentMemory(agent_id=agent_id)

        self._persistent_memories[agent_id] = memory
        return memory

    def save_persistent_memory(self, agent_id: str = "default"):
        """Persist agent memory to disk."""
        memory = self._persistent_memories.get(agent_id)
        if not memory:
            return
        mem_file = self.storage_path / f"persistent_{agent_id}.json"
        mem_file.write_text(json.dumps({
            "agent_id": memory.agent_id,
            "preferences": memory.preferences,
            "learned_patterns": memory.learned_patterns,
            "workflow_templates": memory.workflow_templates,
            "evaluation_history": memory.evaluation_history,
            "version": memory.version,
        }, indent=2, default=str))

    def record_learned_pattern(self, agent_id: str, pattern: dict):
        """Record a learned pattern in persistent memory."""
        memory = self.get_persistent_memory(agent_id)
        pattern["recorded_at"] = datetime.now(timezone.utc).isoformat()
        memory.learned_patterns.append(pattern)
        self.save_persistent_memory(agent_id)

    def record_evaluation(self, agent_id: str, evaluation: dict):
        """Record an evaluation cycle result."""
        memory = self.get_persistent_memory(agent_id)
        evaluation["recorded_at"] = datetime.now(timezone.utc).isoformat()
        memory.evaluation_history.append(evaluation)
        self.save_persistent_memory(agent_id)

    # --- Vault Freshness Tracking ---

    def get_vault_checksum(self, note_path: str) -> Optional[str]:
        """Get the stored checksum for a vault note."""
        return self._vault_checksums.get(note_path)

    def vault_note_changed(self, note_path: str, current_checksum: str) -> bool:
        """Check if a vault note has changed since last read."""
        stored = self._vault_checksums.get(note_path)
        return stored is not None and stored != current_checksum

    def update_vault_checksum(self, note_path: str, content: str):
        """Update the checksum for a vault note after reading it."""
        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]
        self._vault_checksums[note_path] = checksum
