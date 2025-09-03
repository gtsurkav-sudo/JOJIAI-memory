"""High-level chat integration for MemoryAgent.

This module provides a thin wrapper around :class:`memory_agent.MemoryAgent`
so that a chat application can easily persist conversation events and other
context into the JSON memory files.  Each helper method delegates to
``MemoryAgent.update_memory`` which takes care of file locking and timestamp
management.
"""
from __future__ import annotations

from typing import Any

from memory_agent import MemoryAgent


class ChatMemory:
    """Helper that updates memory files in response to chat events."""

    def __init__(self, agent: MemoryAgent | None = None) -> None:
        self.agent = agent or MemoryAgent()

    def log_message(self, role: str, content: str, user_id: str | None = None) -> None:
        """Record a chat message in the logs memory segment."""
        entry = {"role": role, "content": content}
        if user_id is not None:
            entry["user_id"] = user_id
        self.agent.update_memory("logs", entry)

    def record_decision(self, decision: str, **details: Any) -> None:
        """Append a decision to the decisions memory segment."""
        entry = {"decision": decision, **details}
        self.agent.update_memory("decisions", entry)

    def update_profile(self, **profile_data: Any) -> None:
        """Merge ``profile_data`` into the profile memory segment."""
        self.agent.update_memory("profile", profile_data)

    def update_project(self, project_id: str, **project_data: Any) -> None:
        """Create or merge a project in the projects memory segment."""
        entry = {"project_id": project_id, **project_data}
        self.agent.update_memory("projects", entry)


__all__ = ["ChatMemory"]
