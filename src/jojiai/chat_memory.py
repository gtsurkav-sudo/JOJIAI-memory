
"""Chat Memory component for JOJI Oi system."""

import json
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from .exceptions import MemoryError, InvalidSegment
from .validation import validate_segment, sanitize_input
from .file_lock import FileLock, atomic_write, with_retry
from .memory_agent import MemoryAgent

logger = logging.getLogger(__name__)


class ChatMemory:
    """Thread-safe chat memory with conversation management."""
    
    def __init__(self, memory_path: str, config: Optional[Dict[str, Any]] = None):
        """Initialize chat memory.
        
        Args:
            memory_path: Path to memory storage
            config: Optional configuration
        """
        self.memory_path = Path(memory_path)
        self.config = config or {}
        
        # Initialize memory agent
        self.memory_agent = MemoryAgent(str(self.memory_path), config)
        
        # Chat-specific files
        self.session_file = self.memory_path / 'session_buffer.md'
        self.conversations_file = self.memory_path / 'conversations.json'
        
        # Initialize chat files
        self._initialize_chat_files()
        
        logger.info(f"ChatMemory initialized: {self.memory_path}")
    
    def _initialize_chat_files(self) -> None:
        """Initialize chat-specific files."""
        if not self.session_file.exists():
            with atomic_write(str(self.session_file)) as f:
                f.write("# Chat Session Buffer\n\n")
        
        if not self.conversations_file.exists():
            with atomic_write(str(self.conversations_file)) as f:
                json.dump([], f, indent=2)
    
    @with_retry(max_retries=3, delay=0.1)
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add message to chat memory.
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Message ID
            
        Raises:
            MemoryError: If message storage fails
            InvalidSegment: If message is invalid
        """
        # Sanitize input
        role = sanitize_input(role)
        content = sanitize_input(content)
        metadata = sanitize_input(metadata) if metadata else {}
        
        # Validate role
        valid_roles = ['user', 'assistant', 'system']
        if role not in valid_roles:
            raise InvalidSegment(f"Invalid role: {role}. Must be one of {valid_roles}")
        
        # Validate content
        if not content or not content.strip():
            raise InvalidSegment("Message content cannot be empty")
        
        # Create message
        message = {
            'role': role,
            'content': content,
            'timestamp': time.time(),
            'metadata': metadata
        }
        
        # Store as dialogue
        message_id = self.memory_agent.store_dialogue(message)
        
        # Update session buffer
        self._update_session_buffer(role, content)
        
        logger.debug(f"Message added: {message_id}")
        return message_id
    
    @with_retry(max_retries=3, delay=0.1)
    def get_conversation_history(self, limit: Optional[int] = None, 
                               role_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get conversation history.
        
        Args:
            limit: Maximum number of messages to return
            role_filter: Filter by role (user, assistant, system)
            
        Returns:
            List of messages
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            # Get dialogues from memory agent
            dialogues = self.memory_agent.get_dialogues(limit)
            
            # Parse and filter messages
            messages = []
            for dialogue in dialogues:
                try:
                    content = json.loads(dialogue['content'])
                    if isinstance(content, dict) and 'role' in content:
                        if role_filter is None or content['role'] == role_filter:
                            messages.append(content)
                except (json.JSONDecodeError, KeyError):
                    continue
            
            # Sort by timestamp
            messages.sort(key=lambda x: x.get('timestamp', 0))
            
            # Apply limit
            if limit:
                messages = messages[-limit:]
            
            return messages
            
        except Exception as e:
            raise MemoryError(f"Failed to get conversation history: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def get_context_window(self, window_size: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation context.
        
        Args:
            window_size: Number of recent messages to include
            
        Returns:
            Recent messages for context
            
        Raises:
            MemoryError: If context retrieval fails
        """
        return self.get_conversation_history(limit=window_size)
    
    @with_retry(max_retries=3, delay=0.1)
    def search_messages(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search messages by content.
        
        Args:
            query: Search query
            content_limit: Maximum number of results
            
        Returns:
            Matching messages
            
        Raises:
            MemoryError: If search fails
        """
        try:
            query = sanitize_input(query).lower()
            if not query:
                return []
            
            # Get all messages
            messages = self.get_conversation_history()
            
            # Search in content
            matching_messages = []
            for message in messages:
                content = message.get('content', '').lower()
                if query in content:
                    matching_messages.append(message)
            
            # Sort by relevance (timestamp for now)
            matching_messages.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
            return matching_messages[:limit]
            
        except Exception as e:
            raise MemoryError(f"Failed to search messages: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def create_conversation_summary(self, message_count: int = 50) -> str:
        """Create summary of recent conversation.
        
        Args:
            message_count: Number of recent messages to summarize
            
        Returns:
            Conversation summary
            
        Raises:
            MemoryError: If summary creation fails
        """
        try:
            messages = self.get_conversation_history(limit=message_count)
            
            if not messages:
                return "No conversation history available."
            
            # Create basic summary
            summary_parts = []
            summary_parts.append(f"Conversation Summary ({len(messages)} messages)")
            summary_parts.append("=" * 50)
            
            # Group by role
            role_counts = {}
            for message in messages:
                role = message.get('role', 'unknown')
                role_counts[role] = role_counts.get(role, 0) + 1
            
            summary_parts.append("Message distribution:")
            for role, count in role_counts.items():
                summary_parts.append(f"  {role}: {count} messages")
            
            # Time range
            if messages:
                start_time = min(msg.get('timestamp', 0) for msg in messages)
                end_time = max(msg.get('timestamp', 0) for msg in messages)
                duration = end_time - start_time
                summary_parts.append(f"Time span: {duration:.1f} seconds")
            
            # Recent messages preview
            summary_parts.append("\nRecent messages:")
            for message in messages[-5:]:
                role = message.get('role', 'unknown')
                content = message.get('content', '')[:100]
                if len(message.get('content', '')) > 100:
                    content += "..."
                summary_parts.append(f"  {role}: {content}")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            raise MemoryError(f"Failed to create conversation summary: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def _update_session_buffer(self, role: str, content: str) -> None:
        """Update session buffer with new message.
        
        Args:
            role: Message role
            content: Message content
        """
        try:
            lock_file = str(self.memory_path / '.locks' / 'session.lock')
            with FileLock(lock_file, timeout=5.0):
                # Read current buffer
                current_content = ""
                if self.session_file.exists():
                    with open(self.session_file, 'r') as f:
                        current_content = f.read()
                
                # Add new message
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                new_entry = f"\n## {role.title()} ({timestamp})\n\n{content}\n"
                
                # Limit buffer size
                max_buffer_size = self.config.get('max_buffer_size', 50000)  # 50KB
                updated_content = current_content + new_entry
                
                if len(updated_content) > max_buffer_size:
                    # Keep only recent content
                    lines = updated_content.split('\n')
                    while len('\n'.join(lines)) > max_buffer_size and len(lines) > 10:
                        lines.pop(0)
                    updated_content = '\n'.join(lines)
                
                # Write back
                with atomic_write(str(self.session_file)) as f:
                    f.write(updated_content)
                    
        except Exception as e:
            logger.warning(f"Failed to update session buffer: {e}")
    
    def get_session_buffer(self) -> str:
        """Get current session buffer content.
        
        Returns:
            Session buffer content
        """
        try:
            if self.session_file.exists():
                with open(self.session_file, 'r') as f:
                    return f.read()
            return "# Chat Session Buffer\n\n"
        except Exception as e:
            logger.error(f"Failed to read session buffer: {e}")
            return "# Chat Session Buffer\n\nError reading buffer."
    
    def clear_session_buffer(self) -> None:
        """Clear session buffer."""
        try:
            with atomic_write(str(self.session_file)) as f:
                f.write("# Chat Session Buffer\n\n")
            logger.info("Session buffer cleared")
        except Exception as e:
            logger.error(f"Failed to clear session buffer: {e}")
    
    def get_chat_stats(self) -> Dict[str, Any]:
        """Get chat statistics.
        
        Returns:
            Chat statistics
        """
        try:
            messages = self.get_conversation_history()
            
            # Role distribution
            role_counts = {}
            for message in messages:
                role = message.get('role', 'unknown')
                role_counts[role] = role_counts.get(role, 0) + 1
            
            # Time analysis
            timestamps = [msg.get('timestamp', 0) for msg in messages if msg.get('timestamp')]
            time_span = max(timestamps) - min(timestamps) if timestamps else 0
            
            stats = {
                'total_messages': len(messages),
                'role_distribution': role_counts,
                'time_span_seconds': time_span,
                'session_buffer_size': len(self.get_session_buffer()),
                'memory_stats': self.memory_agent.get_memory_stats()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get chat stats: {e}")
            return {}
    
    def close(self) -> None:
        """Close chat memory and cleanup resources."""
        try:
            self.memory_agent.close()
            logger.info("ChatMemory closed")
        except Exception as e:
            logger.error(f"Error closing ChatMemory: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
