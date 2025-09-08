
"""Write-Ahead Log implementation for JOJI Oi system."""

import os
import json
import time
import logging
import threading
from typing import Any, Dict, List, Optional
from pathlib import Path
from .exceptions import WALError, FileOperationError
from .file_lock import FileLock, atomic_write, with_retry

logger = logging.getLogger(__name__)


class WALEntry:
    """Write-Ahead Log entry."""
    
    def __init__(self, operation: str, data: Dict[str, Any], timestamp: Optional[float] = None):
        """Initialize WAL entry.
        
        Args:
            operation: Operation type (INSERT, UPDATE, DELETE)
            data: Operation data
            timestamp: Entry timestamp
        """
        self.operation = operation
        self.data = data
        self.timestamp = timestamp or time.time()
        self.id = f"{self.timestamp}_{hash(json.dumps(data, sort_keys=True))}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            'id': self.id,
            'operation': self.operation,
            'data': self.data,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WALEntry':
        """Create entry from dictionary."""
        entry = cls(data['operation'], data['data'], data['timestamp'])
        entry.id = data['id']
        return entry


class WriteAheadLog:
    """Write-Ahead Log for ensuring data consistency."""
    
    def __init__(self, wal_path: str, flush_interval: float = 5.0):
        """Initialize WAL.
        
        Args:
            wal_path: Path to WAL file
            flush_interval: Automatic flush interval in seconds
        """
        self.wal_path = Path(wal_path)
        self.flush_interval = flush_interval
        self.lock_path = str(self.wal_path) + '.lock'
        
        # Create WAL directory if it doesn't exist
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize WAL file if it doesn't exist
        if not self.wal_path.exists():
            with atomic_write(str(self.wal_path)) as f:
                json.dump([], f)
        
        # Start background flush thread
        self._stop_flush = threading.Event()
        self._flush_thread = threading.Thread(target=self._background_flush, daemon=True)
        self._flush_thread.start()
        
        logger.info(f"WAL initialized: {self.wal_path}")
    
    @with_retry(max_retries=3, delay=0.1)
    def append(self, operation: str, data: Dict[str, Any]) -> str:
        """Append entry to WAL.
        
        Args:
            operation: Operation type
            data: Operation data
            
        Returns:
            Entry ID
            
        Raises:
            WALError: If append fails
        """
        entry = WALEntry(operation, data)
        
        try:
            with FileLock(self.lock_path, timeout=10.0):
                # Read current WAL
                with open(self.wal_path, 'r') as f:
                    wal_data = json.load(f)
                
                # Append new entry
                wal_data.append(entry.to_dict())
                
                # Write back to WAL
                with atomic_write(str(self.wal_path)) as f:
                    json.dump(wal_data, f, indent=2)
                
                logger.debug(f"WAL entry appended: {entry.id}")
                return entry.id
                
        except Exception as e:
            raise WALError(f"Failed to append WAL entry: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def read_entries(self, since_timestamp: Optional[float] = None) -> List[WALEntry]:
        """Read WAL entries.
        
        Args:
            since_timestamp: Only return entries after this timestamp
            
        Returns:
            List of WAL entries
            
        Raises:
            WALError: If read fails
        """
        try:
            with FileLock(self.lock_path, timeout=10.0):
                with open(self.wal_path, 'r') as f:
                    wal_data = json.load(f)
                
                entries = [WALEntry.from_dict(entry_data) for entry_data in wal_data]
                
                if since_timestamp is not None:
                    entries = [entry for entry in entries if entry.timestamp > since_timestamp]
                
                return entries
                
        except Exception as e:
            raise WALError(f"Failed to read WAL entries: {e}")
    
    @with_retry(max_retries=3, delay=0.1)
    def truncate(self, before_timestamp: float) -> int:
        """Remove WAL entries before specified timestamp.
        
        Args:
            before_timestamp: Remove entries before this timestamp
            
        Returns:
            Number of entries removed
            
        Raises:
            WALError: If truncate fails
        """
        try:
            with FileLock(self.lock_path, timeout=10.0):
                with open(self.wal_path, 'r') as f:
                    wal_data = json.load(f)
                
                original_count = len(wal_data)
                wal_data = [entry for entry in wal_data if entry['timestamp'] >= before_timestamp]
                removed_count = original_count - len(wal_data)
                
                with atomic_write(str(self.wal_path)) as f:
                    json.dump(wal_data, f, indent=2)
                
                logger.info(f"WAL truncated: removed {removed_count} entries")
                return removed_count
                
        except Exception as e:
            raise WALError(f"Failed to truncate WAL: {e}")
    
    def flush(self) -> None:
        """Force flush WAL to disk."""
        try:
            # WAL is already flushed on each write due to atomic_write
            # This method is for compatibility and future enhancements
            logger.debug("WAL flush completed")
        except Exception as e:
            logger.warning(f"WAL flush warning: {e}")
    
    def _background_flush(self) -> None:
        """Background thread for periodic WAL maintenance."""
        while not self._stop_flush.wait(self.flush_interval):
            try:
                # Perform periodic maintenance
                current_time = time.time()
                old_threshold = current_time - (7 * 24 * 3600)  # 7 days
                
                # Remove old entries
                removed = self.truncate(old_threshold)
                if removed > 0:
                    logger.info(f"WAL maintenance: removed {removed} old entries")
                    
            except Exception as e:
                logger.error(f"WAL background maintenance error: {e}")
    
    def close(self) -> None:
        """Close WAL and cleanup resources."""
        self._stop_flush.set()
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)
        logger.info("WAL closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
