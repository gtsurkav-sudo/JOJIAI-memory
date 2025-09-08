
"""Backup and recovery system for JOJI Oi."""

import os
import json
import time
import shutil
import logging
import threading
from typing import Any, Dict, List, Optional
from pathlib import Path
from .exceptions import BackupError, RecoveryError
from .file_lock import FileLock, atomic_write, with_retry
from .wal import WriteAheadLog

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages backup and recovery operations."""
    
    def __init__(self, data_path: str, backup_path: str, wal_path: str, 
                 backup_interval: float = 3600.0):
        """Initialize backup manager.
        
        Args:
            data_path: Path to main data directory
            backup_path: Path to backup directory
            wal_path: Path to WAL file
            backup_interval: Backup interval in seconds
        """
        self.data_path = Path(data_path)
        self.backup_path = Path(backup_path)
        self.wal_path = Path(wal_path)
        self.backup_interval = backup_interval
        
        # Create directories
        self.backup_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize WAL
        self.wal = WriteAheadLog(str(self.wal_path))
        
        # Start background backup thread
        self._stop_backup = threading.Event()
        self._backup_thread = threading.Thread(target=self._background_backup, daemon=True)
        self._backup_thread.start()
        
        logger.info(f"Backup manager initialized: {self.backup_path}")
    
    @with_retry(max_retries=3, delay=1.0)
    def create_snapshot(self, snapshot_name: Optional[str] = None) -> str:
        """Create a snapshot of current data.
        
        Args:
            snapshot_name: Optional snapshot name
            
        Returns:
            Snapshot identifier
            
        Raises:
            BackupError: If snapshot creation fails
        """
        if snapshot_name is None:
            snapshot_name = f"snapshot_{int(time.time())}"
        
        snapshot_dir = self.backup_path / snapshot_name
        
        try:
            # Create snapshot directory
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy data files
            if self.data_path.exists():
                for item in self.data_path.iterdir():
                    if item.is_file() and item.suffix in ['.json', '.md', '.txt']:
                        shutil.copy2(item, snapshot_dir / item.name)
            
            # Create snapshot metadata
            metadata = {
                'snapshot_name': snapshot_name,
                'timestamp': time.time(),
                'data_path': str(self.data_path),
                'files_count': len(list(snapshot_dir.glob('*'))),
                'wal_position': self._get_wal_position()
            }
            
            with atomic_write(str(snapshot_dir / 'metadata.json')) as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Snapshot created: {snapshot_name}")
            return snapshot_name
            
        except Exception as e:
            # Cleanup on failure
            if snapshot_dir.exists():
                shutil.rmtree(snapshot_dir, ignore_errors=True)
            raise BackupError(f"Failed to create snapshot {snapshot_name}: {e}")
    
    @with_retry(max_retries=3, delay=1.0)
    def restore_snapshot(self, snapshot_name: str, target_path: Optional[str] = None) -> None:
        """Restore data from snapshot.
        
        Args:
            snapshot_name: Snapshot to restore
            target_path: Optional target path (defaults to original data path)
            
        Raises:
            RecoveryError: If restore fails
        """
        snapshot_dir = self.backup_path / snapshot_name
        
        if not snapshot_dir.exists():
            raise RecoveryError(f"Snapshot not found: {snapshot_name}")
        
        target = Path(target_path) if target_path else self.data_path
        
        try:
            # Read snapshot metadata
            metadata_file = snapshot_dir / 'metadata.json'
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                logger.info(f"Restoring snapshot from {metadata['timestamp']}")
            
            # Create target directory
            target.mkdir(parents=True, exist_ok=True)
            
            # Restore files
            restored_count = 0
            for item in snapshot_dir.iterdir():
                if item.name != 'metadata.json' and item.is_file():
                    shutil.copy2(item, target / item.name)
                    restored_count += 1
            
            logger.info(f"Snapshot restored: {snapshot_name} ({restored_count} files)")
            
        except Exception as e:
            raise RecoveryError(f"Failed to restore snapshot {snapshot_name}: {e}")
    
    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List available snapshots.
        
        Returns:
            List of snapshot information
        """
        snapshots = []
        
        try:
            for snapshot_dir in self.backup_path.iterdir():
                if snapshot_dir.is_dir():
                    metadata_file = snapshot_dir / 'metadata.json'
                    if metadata_file.exists():
                        try:
                            with open(metadata_file, 'r') as f:
                                metadata = json.load(f)
                            snapshots.append(metadata)
                        except Exception as e:
                            logger.warning(f"Failed to read snapshot metadata {snapshot_dir}: {e}")
                    else:
                        # Create basic metadata for snapshots without metadata
                        snapshots.append({
                            'snapshot_name': snapshot_dir.name,
                            'timestamp': snapshot_dir.stat().st_mtime,
                            'files_count': len(list(snapshot_dir.glob('*')))
                        })
            
            # Sort by timestamp (newest first)
            snapshots.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list snapshots: {e}")
        
        return snapshots
    
    def cleanup_old_snapshots(self, keep_count: int = 10) -> int:
        """Remove old snapshots, keeping only the most recent ones.
        
        Args:
            keep_count: Number of snapshots to keep
            
        Returns:
            Number of snapshots removed
        """
        snapshots = self.list_snapshots()
        removed_count = 0
        
        if len(snapshots) > keep_count:
            snapshots_to_remove = snapshots[keep_count:]
            
            for snapshot in snapshots_to_remove:
                snapshot_name = snapshot['snapshot_name']
                snapshot_dir = self.backup_path / snapshot_name
                
                try:
                    if snapshot_dir.exists():
                        shutil.rmtree(snapshot_dir)
                        removed_count += 1
                        logger.info(f"Removed old snapshot: {snapshot_name}")
                except Exception as e:
                    logger.warning(f"Failed to remove snapshot {snapshot_name}: {e}")
        
        return removed_count
    
    def recover_from_wal(self, target_path: Optional[str] = None, 
                        since_timestamp: Optional[float] = None) -> int:
        """Recover data by replaying WAL entries.
        
        Args:
            target_path: Target path for recovery
            since_timestamp: Only replay entries after this timestamp
            
        Returns:
            Number of entries replayed
            
        Raises:
            RecoveryError: If recovery fails
        """
        try:
            entries = self.wal.read_entries(since_timestamp)
            target = Path(target_path) if target_path else self.data_path
            
            replayed_count = 0
            for entry in entries:
                try:
                    self._replay_wal_entry(entry, target)
                    replayed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to replay WAL entry {entry.id}: {e}")
            
            logger.info(f"WAL recovery completed: {replayed_count} entries replayed")
            return replayed_count
            
        except Exception as e:
            raise RecoveryError(f"WAL recovery failed: {e}")
    
    def _replay_wal_entry(self, entry, target_path: Path) -> None:
        """Replay a single WAL entry."""
        operation = entry.operation
        data = entry.data
        
        if operation == 'INSERT' or operation == 'UPDATE':
            file_path = target_path / data.get('file', 'unknown.json')
            with atomic_write(str(file_path)) as f:
                json.dump(data.get('content', {}), f, indent=2)
        
        elif operation == 'DELETE':
            file_path = target_path / data.get('file', 'unknown.json')
            if file_path.exists():
                file_path.unlink()
    
    def _get_wal_position(self) -> int:
        """Get current WAL position."""
        try:
            entries = self.wal.read_entries()
            return len(entries)
        except Exception:
            return 0
    
    def _background_backup(self) -> None:
        """Background thread for automatic backups."""
        while not self._stop_backup.wait(self.backup_interval):
            try:
                snapshot_name = f"auto_{int(time.time())}"
                self.create_snapshot(snapshot_name)
                
                # Cleanup old snapshots
                self.cleanup_old_snapshots(keep_count=10)
                
            except Exception as e:
                logger.error(f"Background backup error: {e}")
    
    def close(self) -> None:
        """Close backup manager and cleanup resources."""
        self._stop_backup.set()
        if self._backup_thread.is_alive():
            self._backup_thread.join(timeout=5.0)
        
        if hasattr(self, 'wal'):
            self.wal.close()
        
        logger.info("Backup manager closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
