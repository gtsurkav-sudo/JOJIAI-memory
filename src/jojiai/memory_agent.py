
"""Memory Agent for JOJI Oi system with race condition fixes."""

import json
import time
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
from .exceptions import MemoryError, InvalidSegment, ConcurrencyError
from .validation import validate_segment, sanitize_input
from .file_lock import FileLock, atomic_write, with_retry
from .wal import WriteAheadLog
from .backup import BackupManager

logger = logging.getLogger(__name__)


class MemoryAgent:
    """Thread-safe memory agent with WAL and backup support."""
    
    def __init__(self, memory_path: str, config: Optional[Dict[str, Any]] = None):
        """Initialize memory agent.
        
        Args:
            memory_path: Path to memory storage directory
            config: Optional configuration
        """
        self.memory_path = Path(memory_path)
        self.config = config or {}
        
        # Create memory directory
        self.memory_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize file paths
        self.dialogues_file = self.memory_path / 'memory_dialogues_v2.json'
        self.decisions_file = self.memory_path / 'memory_decisions_v2.json'
        self.profile_file = self.memory_path / 'memory_profile_v2.json'
        self.projects_file = self.memory_path / 'memory_projects_v2.json'
        
        # Initialize lock files
        self.lock_dir = self.memory_path / '.locks'
        self.lock_dir.mkdir(exist_ok=True)
        
        # Initialize WAL and backup
        wal_path = self.memory_path / 'memory.wal'
        backup_path = self.memory_path / 'backups'
        
        self.wal = WriteAheadLog(str(wal_path))
        self.backup_manager = BackupManager(
            str(self.memory_path),
            str(backup_path),
            str(wal_path)
        )
        
        # Initialize memory files
        self._initialize_memory_files()
        
        logger.info(f"MemoryAgent initialized: {self.memory_path}")
    
    def _initialize_memory_files(self) -> None:
        """Initialize memory files if they don't exist."""
        default_files = {
            self.dialogues_file: [],
            self.decisions_file: [],
            self.profile_file: {},
            self.projects_file: []
        }
        
        for file_path, default_content in default_files.items():
            if not file_path.exists():
                try:
                    with atomic_write(str(file_path)) as f:
                        json.dump(default_content, f, indent=2)
                    logger.debug(f"Initialized memory file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to initialize {file_path}: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def store_dialogue(self, dialogue: Dict[str, Any]) -> str:
        """Store dialogue segment with race condition protection.
        
        Args:
            dialogue: Dialogue data to store
            
        Returns:
            Dialogue ID
            
        Raises:
            MemoryError: If storage fails
            InvalidSegment: If dialogue is invalid
        """
        # Sanitize and validate input
        dialogue = sanitize_input(dialogue)
        
        # Add metadata
        dialogue_id = f"dialogue_{int(time.time() * 1000)}"
        segment = {
            'id': dialogue_id,
            'content': json.dumps(dialogue),
            'timestamp': time.time(),
            'type': 'dialogue'
        }
        
        # Validate segment
        validate_segment(segment)
        
        try:
            # Log to WAL first
            self.wal.append('INSERT', {
                'file': 'memory_dialogues_v2.json',
                'content': segment
            })
            
            # Store with file locking
            lock_file = str(self.lock_dir / 'dialogues.lock')
            with FileLock(lock_file, timeout=10.0):
                # Read current data
                with open(self.dialogues_file, 'r') as f:
                    dialogues = json.load(f)
                
                # Add new dialogue
                dialogues.append(segment)
                
                # Limit memory size
                max_dialogues = self.config.get('max_dialogues', 1000)
                if len(dialogues) > max_dialogues:
                    dialogues = dialogues[-max_dialogues:]
                
                # Write back atomically
                with atomic_write(str(self.dialogues_file)) as f:
                    json.dump(dialogues, f, indent=2)
            
            logger.info(f"Dialogue stored: {dialogue_id}")
            return dialogue_id
            
        except Exception as e:
            raise MemoryError(f"Failed to store dialogue: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def store_decision(self, decision: Dict[str, Any]) -> str:
        """Store decision segment with race condition protection.
        
        Args:
            decision: Decision data to store
            
        Returns:
            Decision ID
            
        Raises:
            MemoryError: If storage fails
            InvalidSegment: If decision is invalid
        """
        # Sanitize and validate input
        decision = sanitize_input(decision)
        
        # Add metadata
        decision_id = f"decision_{int(time.time() * 1000)}"
        segment = {
            'id': decision_id,
            'content': json.dumps(decision),
            'timestamp': time.time(),
            'type': 'decision'
        }
        
        # Validate segment
        validate_segment(segment)
        
        try:
            # Log to WAL first
            self.wal.append('INSERT', {
                'file': 'memory_decisions_v2.json',
                'content': segment
            })
            
            # Store with file locking
            lock_file = str(self.lock_dir / 'decisions.lock')
            with FileLock(lock_file, timeout=10.0):
                # Read current data
                with open(self.decisions_file, 'r') as f:
                    decisions = json.load(f)
                
                # Add new decision
                decisions.append(segment)
                
                # Limit memory size
                max_decisions = self.config.get('max_decisions', 500)
                if len(decisions) > max_decisions:
                    decisions = decisions[-max_decisions:]
                
                # Write back atomically
                with atomic_write(str(self.decisions_file)) as f:
                    json.dump(decisions, f, indent=2)
            
            logger.info(f"Decision stored: {decision_id}")
            return decision_id
            
        except Exception as e:
            raise MemoryError(f"Failed to store decision: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def update_profile(self, profile_data: Dict[str, Any]) -> None:
        """Update profile with race condition protection.
        
        Args:
            profile_data: Profile data to update
            
        Raises:
            MemoryError: If update fails
            InvalidSegment: If profile data is invalid
        """
        # Sanitize and validate input
        profile_data = sanitize_input(profile_data)
        
        # Create segment for validation
        segment = {
            'id': 'profile_update',
            'content': json.dumps(profile_data),
            'timestamp': time.time(),
            'type': 'profile'
        }
        
        # Validate segment
        validate_segment(segment)
        
        try:
            # Log to WAL first
            self.wal.append('UPDATE', {
                'file': 'memory_profile_v2.json',
                'content': profile_data
            })
            
            # Update with file locking
            lock_file = str(self.lock_dir / 'profile.lock')
            with FileLock(lock_file, timeout=10.0):
                # Read current profile
                current_profile = {}
                if self.profile_file.exists():
                    with open(self.profile_file, 'r') as f:
                        current_profile = json.load(f)
                
                # Merge profile data
                current_profile.update(profile_data)
                current_profile['last_updated'] = time.time()
                
                # Write back atomically
                with atomic_write(str(self.profile_file)) as f:
                    json.dump(current_profile, f, indent=2)
            
            logger.info("Profile updated successfully")
            
        except Exception as e:
            raise MemoryError(f"Failed to update profile: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def get_dialogues(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve dialogues with race condition protection.
        
        Args:
            limit: Maximum number of dialogues to return
            
        Returns:
            List of dialogue segments
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            lock_file = str(self.lock_dir / 'dialogues.lock')
            with FileLock(lock_file, timeout=5.0):
                if not self.dialogues_file.exists():
                    return []
                
                with open(self.dialogues_file, 'r') as f:
                    dialogues = json.load(f)
                
                # Apply limit
                if limit:
                    dialogues = dialogues[-limit:]
                
                return dialogues
                
        except Exception as e:
            raise MemoryError(f"Failed to retrieve dialogues: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def get_decisions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve decisions with race condition protection.
        
        Args:
            limit: Maximum number of decisions to return
            
        Returns:
            List of decision segments
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            lock_file = str(self.lock_dir / 'decisions.lock')
            with FileLock(lock_file, timeout=5.0):
                if not self.decisions_file.exists():
                    return []
                
                with open(self.decisions_file, 'r') as f:
                    decisions = json.load(f)
                
                # Apply limit
                if limit:
                    decisions = decisions[-limit:]
                
                return decisions
                
        except Exception as e:
            raise MemoryError(f"Failed to retrieve decisions: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def get_profile(self) -> Dict[str, Any]:
        """Retrieve profile with race condition protection.
        
        Returns:
            Profile data
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            lock_file = str(self.lock_dir / 'profile.lock')
            with FileLock(lock_file, timeout=5.0):
                if not self.profile_file.exists():
                    return {}
                
                with open(self.profile_file, 'r') as f:
                    return json.load(f)
                
        except Exception as e:
            raise MemoryError(f"Failed to retrieve profile: {e}")
    
    def create_snapshot(self, snapshot_name: Optional[str] = None) -> str:
        """Create memory snapshot.
        
        Args:
            snapshot_name: Optional snapshot name
            
        Returns:
            Snapshot identifier
        """
        return self.backup_manager.create_snapshot(snapshot_name)
    
    def restore_snapshot(self, snapshot_name: str) -> None:
        """Restore from snapshot.
        
        Args:
            snapshot_name: Snapshot to restore
        """
        self.backup_manager.restore_snapshot(snapshot_name, str(self.memory_path))
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics.
        
        Returns:
            Memory statistics
        """
        try:
            stats = {
                'dialogues_count': len(self.get_dialogues()),
                'decisions_count': len(self.get_decisions()),
                'profile_keys': len(self.get_profile().keys()),
                'memory_path': str(self.memory_path),
                'wal_entries': len(self.wal.read_entries()),
                'snapshots': len(self.backup_manager.list_snapshots())
            }
            return stats
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {}
    
    def close(self) -> None:
        """Close memory agent and cleanup resources."""
        try:
            self.wal.close()
            self.backup_manager.close()
            logger.info("MemoryAgent closed")
        except Exception as e:
            logger.error(f"Error closing MemoryAgent: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
