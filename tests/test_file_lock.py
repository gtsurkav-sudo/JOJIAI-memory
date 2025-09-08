
"""Tests for file locking utilities."""

import os
import time
import pytest
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

from jojiai.file_lock import FileLock, atomic_write, with_retry
from jojiai.exceptions import ConcurrencyError, FileOperationError


class TestFileLock:
    """Test suite for FileLock."""
    
    @pytest.fixture
    def temp_lock_file(self):
        """Create temporary lock file path."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            lock_path = f.name
        os.unlink(lock_path)  # Remove the file, keep the path
        yield lock_path
        # Cleanup
        try:
            os.unlink(lock_path)
        except OSError:
            pass
    
    def test_lock_acquire_release(self, temp_lock_file):
        """Test basic lock acquire and release."""
        lock = FileLock(temp_lock_file, timeout=5.0)
        
        # Acquire lock
        assert lock.acquire() is True
        assert os.path.exists(temp_lock_file)
        
        # Release lock
        lock.release()
        assert not os.path.exists(temp_lock_file)
    
    def test_context_manager(self, temp_lock_file):
        """Test FileLock as context manager."""
        with FileLock(temp_lock_file, timeout=5.0) as lock:
            assert os.path.exists(temp_lock_file)
            assert lock.lock_fd is not None
        
        # Lock should be released after context exit
        assert not os.path.exists(temp_lock_file)
    
    def test_concurrent_lock_access(self, temp_lock_file):
        """Test concurrent access to the same lock."""
        results = []
        
        def acquire_lock(index):
            try:
                with FileLock(temp_lock_file, timeout=2.0):
                    # Hold lock for a short time
                    time.sleep(0.1)
                    results.append(f"success_{index}")
            except ConcurrencyError:
                results.append(f"timeout_{index}")
            except Exception as e:
                results.append(f"error_{index}_{type(e).__name__}")
        
        # Create multiple threads trying to acquire the same lock
        threads = []
        for i in range(5):
            thread = threading.Thread(target=acquire_lock, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        success_count = len([r for r in results if r.startswith('success_')])
        timeout_count = len([r for r in results if r.startswith('timeout_')])
        
        # All threads should complete (either success or timeout)
        assert len(results) == 5
        # At least one should succeed
        assert success_count >= 1
        # Some may timeout due to concurrent access
        assert success_count + timeout_count == 5
    
    def test_lock_timeout(self, temp_lock_file):
        """Test lock timeout behavior."""
        # First lock acquires successfully
        lock1 = FileLock(temp_lock_file, timeout=1.0)
        assert lock1.acquire() is True
        
        try:
            # Second lock should timeout
            lock2 = FileLock(temp_lock_file, timeout=0.5)
            with pytest.raises(ConcurrencyError):
                lock2.acquire()
        finally:
            lock1.release()
    
    @patch('jojiai.file_lock.fcntl.flock')
    def test_lock_system_error(self, mock_flock, temp_lock_file):
        """Test handling of system errors during locking."""
        # Mock flock to raise a system error
        mock_flock.side_effect = OSError(1, "Operation not permitted")
        
        lock = FileLock(temp_lock_file, timeout=1.0)
        with pytest.raises(FileOperationError):
            lock.acquire()
    
    def test_lock_file_cleanup_on_error(self, temp_lock_file):
        """Test lock file cleanup when errors occur."""
        with patch('jojiai.file_lock.fcntl.flock') as mock_flock:
            # Mock flock to raise an error after file creation
            mock_flock.side_effect = OSError(1, "Test error")
            
            lock = FileLock(temp_lock_file, timeout=1.0)
            
            with pytest.raises(FileOperationError):
                lock.acquire()
            
            # Lock file descriptor should be cleaned up
            assert lock.lock_fd is None


class TestAtomicWrite:
    """Test suite for atomic_write."""
    
    @pytest.fixture
    def temp_file_path(self):
        """Create temporary file path."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            file_path = f.name
        os.unlink(file_path)  # Remove the file, keep the path
        yield file_path
        # Cleanup
        try:
            os.unlink(file_path)
        except OSError:
            pass
    
    def test_atomic_write_success(self, temp_file_path):
        """Test successful atomic write."""
        test_content = "This is test content"
        
        with atomic_write(temp_file_path) as f:
            f.write(test_content)
        
        # Verify file was created with correct content
        assert os.path.exists(temp_file_path)
        with open(temp_file_path, 'r') as f:
            assert f.read() == test_content
    
    def test_atomic_write_failure_cleanup(self, temp_file_path):
        """Test cleanup on atomic write failure."""
        with pytest.raises(ValueError):
            with atomic_write(temp_file_path) as f:
                f.write("Some content")
                raise ValueError("Test error")
        
        # Original file should not exist
        assert not os.path.exists(temp_file_path)
    
    def test_atomic_write_binary_mode(self, temp_file_path):
        """Test atomic write in binary mode."""
        test_content = b"Binary test content"
        
        with atomic_write(temp_file_path, mode='wb') as f:
            f.write(test_content)
        
        # Verify file was created with correct content
        with open(temp_file_path, 'rb') as f:
            assert f.read() == test_content
    
    def test_atomic_write_existing_file(self, temp_file_path):
        """Test atomic write replacing existing file."""
        # Create initial file
        initial_content = "Initial content"
        with open(temp_file_path, 'w') as f:
            f.write(initial_content)
        
        # Atomically replace with new content
        new_content = "New content"
        with atomic_write(temp_file_path) as f:
            f.write(new_content)
        
        # Verify file was replaced
        with open(temp_file_path, 'r') as f:
            assert f.read() == new_content
    
    def test_atomic_write_concurrent_access(self, temp_file_path):
        """Test atomic write under concurrent access."""
        results = []
        
        def write_file(content):
            try:
                with atomic_write(temp_file_path) as f:
                    f.write(content)
                    time.sleep(0.1)  # Simulate some processing time
                results.append(f"success_{content}")
            except Exception as e:
                results.append(f"error_{content}_{type(e).__name__}")
        
        # Create multiple threads writing to the same file
        threads = []
        for i in range(3):
            content = f"content_{i}"
            thread = threading.Thread(target=write_file, args=(content,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All writes should succeed
        assert len(results) == 3
        assert all(r.startswith('success_') for r in results)
        
        # File should contain one of the written contents
        with open(temp_file_path, 'r') as f:
            final_content = f.read()
            assert final_content in ['content_0', 'content_1', 'content_2']


class TestWithRetry:
    """Test suite for with_retry decorator."""
    
    def test_retry_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        call_count = 0
        
        @with_retry(max_retries=3, delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = test_function()
        assert result == "success"
        assert call_count == 1
    
    def test_retry_success_after_failures(self):
        """Test successful execution after some failures."""
        call_count = 0
        
        @with_retry(max_retries=3, delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConcurrencyError("Temporary failure")
            return "success"
        
        result = test_function()
        assert result == "success"
        assert call_count == 3
    
    def test_retry_exhaustion(self):
        """Test retry exhaustion."""
        call_count = 0
        
        @with_retry(max_retries=2, delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise ConcurrencyError("Persistent failure")
        
        with pytest.raises(ConcurrencyError):
            test_function()
        
        assert call_count == 3  # Initial attempt + 2 retries
    
    def test_retry_non_recoverable_error(self):
        """Test that non-recoverable errors are not retried."""
        call_count = 0
        
        @with_retry(max_retries=3, delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-recoverable error")
        
        with pytest.raises(ValueError):
            test_function()
        
        assert call_count == 1  # Should not retry
    
    def test_retry_backoff(self):
        """Test exponential backoff behavior."""
        call_times = []
        
        @with_retry(max_retries=2, delay=0.1, backoff=2.0)
        def test_function():
            call_times.append(time.time())
            raise FileOperationError("Test error")
        
        with pytest.raises(FileOperationError):
            test_function()
        
        assert len(call_times) == 3  # Initial + 2 retries
        
        # Check that delays increase (approximately)
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        
        # Second delay should be roughly twice the first
        assert delay2 > delay1 * 1.5
    
    def test_retry_with_different_exceptions(self):
        """Test retry behavior with different exception types."""
        call_count = 0
        
        @with_retry(max_retries=3, delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConcurrencyError("First error")
            elif call_count == 2:
                raise FileOperationError("Second error")
            else:
                return "success"
        
        result = test_function()
        assert result == "success"
        assert call_count == 3
