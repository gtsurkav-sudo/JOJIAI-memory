
"""File locking utilities for concurrent access control."""

import os
import time
import fcntl
import errno
import logging
from typing import Optional, Any
from contextlib import contextmanager
from functools import wraps
from .exceptions import ConcurrencyError, FileOperationError

logger = logging.getLogger(__name__)


class FileLock:
    """Cross-platform file locking implementation."""
    
    def __init__(self, lock_file: str, timeout: float = 30.0):
        """Initialize file lock.
        
        Args:
            lock_file: Path to lock file
            timeout: Maximum time to wait for lock acquisition
        """
        self.lock_file = lock_file
        self.timeout = timeout
        self.lock_fd: Optional[int] = None
        
    def acquire(self) -> bool:
        """Acquire the file lock.
        
        Returns:
            True if lock acquired successfully
            
        Raises:
            ConcurrencyError: If lock cannot be acquired within timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                # Create lock file if it doesn't exist
                self.lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
                
                # Try to acquire exclusive lock
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Write PID to lock file
                os.write(self.lock_fd, str(os.getpid()).encode())
                os.fsync(self.lock_fd)
                
                logger.debug(f"Acquired lock: {self.lock_file}")
                return True
                
            except (OSError, IOError) as e:
                if e.errno in (errno.EAGAIN, errno.EACCES):
                    # Lock is held by another process, wait and retry
                    time.sleep(0.1)
                    continue
                else:
                    # Other error occurred
                    if self.lock_fd is not None:
                        os.close(self.lock_fd)
                        self.lock_fd = None
                    raise FileOperationError(f"Failed to acquire lock: {e}")
        
        # Timeout reached
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None
        raise ConcurrencyError(f"Failed to acquire lock within {self.timeout}s: {self.lock_file}")
    
    def release(self) -> None:
        """Release the file lock."""
        if self.lock_fd is not None:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
                self.lock_fd = None
                
                # Remove lock file
                try:
                    os.unlink(self.lock_file)
                except OSError:
                    pass  # File may have been removed by another process
                    
                logger.debug(f"Released lock: {self.lock_file}")
            except (OSError, IOError) as e:
                logger.warning(f"Error releasing lock {self.lock_file}: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


@contextmanager
def atomic_write(file_path: str, mode: str = 'w', encoding: str = 'utf-8'):
    """Context manager for atomic file writes.
    
    Args:
        file_path: Target file path
        mode: File open mode
        encoding: File encoding
        
    Yields:
        File handle for writing
        
    Raises:
        FileOperationError: If atomic write fails
    """
    import tempfile
    import shutil
    
    temp_path = None
    try:
        # Create temporary file in same directory as target
        dir_path = os.path.dirname(file_path)
        if not dir_path:
            dir_path = '.'
            
        with tempfile.NamedTemporaryFile(
            mode=mode, 
            encoding=encoding if 'b' not in mode else None,
            dir=dir_path,
            delete=False
        ) as temp_file:
            temp_path = temp_file.name
            yield temp_file
            temp_file.flush()
            os.fsync(temp_file.fileno())
        
        # Atomic move to target location
        if os.name == 'nt':  # Windows
            # Windows doesn't support atomic replace if target exists
            if os.path.exists(file_path):
                os.unlink(file_path)
        
        os.replace(temp_path, file_path)
        temp_path = None  # Successfully moved
        
    except Exception as e:
        # Cleanup temporary file on error
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        raise FileOperationError(f"Atomic write failed for {file_path}: {e}")


def with_retry(max_retries: int = 3, delay: float = 0.1, backoff: float = 2.0):
    """Decorator for retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier for delay
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (ConcurrencyError, FileOperationError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
                        break
                except Exception as e:
                    # Don't retry for non-recoverable errors
                    raise e
            
            # All retries exhausted
            raise last_exception
        
        return wrapper
    return decorator
