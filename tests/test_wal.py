
"""Tests for Write-Ahead Log implementation."""

import json
import time
import pytest
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from jojiai.wal import WALEntry, WriteAheadLog
from jojiai.exceptions import WALError


class TestWALEntry:
    """Test suite for WALEntry."""
    
    def test_wal_entry_creation(self):
        """Test WAL entry creation."""
        data = {'key': 'value', 'number': 123}
        entry = WALEntry('INSERT', data)
        
        assert entry.operation == 'INSERT'
        assert entry.data == data
        assert isinstance(entry.timestamp, float)
        assert entry.timestamp > 0
        assert entry.id.startswith(str(int(entry.timestamp)))
    
    def test_wal_entry_with_timestamp(self):
        """Test WAL entry creation with custom timestamp."""
        data = {'key': 'value'}
        custom_timestamp = 1234567890.0
        entry = WALEntry('UPDATE', data, custom_timestamp)
        
        assert entry.timestamp == custom_timestamp
        assert entry.id.startswith('1234567890')
    
    def test_wal_entry_to_dict(self):
        """Test WAL entry serialization to dictionary."""
        data = {'key': 'value', 'nested': {'inner': 'data'}}
        entry = WALEntry('DELETE', data)
        
        entry_dict = entry.to_dict()
        
        assert entry_dict['operation'] == 'DELETE'
        assert entry_dict['data'] == data
        assert entry_dict['timestamp'] == entry.timestamp
        assert entry_dict['id'] == entry.id
    
    def test_wal_entry_from_dict(self):
        """Test WAL entry deserialization from dictionary."""
        entry_dict = {
            'id': 'test_id_123',
            'operation': 'INSERT',
            'data': {'key': 'value'},
            'timestamp': 1234567890.0
        }
        
        entry = WALEntry.from_dict(entry_dict)
        
        assert entry.id == 'test_id_123'
        assert entry.operation == 'INSERT'
        assert entry.data == {'key': 'value'}
        assert entry.timestamp == 1234567890.0
    
    def test_wal_entry_id_uniqueness(self):
        """Test that WAL entry IDs are unique."""
        data = {'key': 'value'}
        entries = []
        
        for i in range(100):
            entry = WALEntry('INSERT', data)
            entries.append(entry)
            time.sleep(0.001)  # Small delay to ensure different timestamps
        
        # All IDs should be unique
        ids = [entry.id for entry in entries]
        assert len(set(ids)) == len(ids)


class TestWriteAheadLog:
    """Test suite for WriteAheadLog."""
    
    @pytest.fixture
    def temp_wal_path(self):
        """Create temporary WAL file path."""
        with tempfile.NamedTemporaryFile(suffix='.wal', delete=False) as f:
            wal_path = f.name
        Path(wal_path).unlink()  # Remove the file, keep the path
        yield wal_path
        # Cleanup
        try:
            Path(wal_path).unlink()
            Path(wal_path + '.lock').unlink()
        except OSError:
            pass
    
    def test_wal_initialization(self, temp_wal_path):
        """Test WAL initialization."""
        with WriteAheadLog(temp_wal_path, flush_interval=1.0) as wal:
            assert Path(temp_wal_path).exists()
            assert wal.wal_path == Path(temp_wal_path)
            assert wal.flush_interval == 1.0
            
            # WAL file should be initialized with empty array
            with open(temp_wal_path, 'r') as f:
                data = json.load(f)
                assert data == []
    
    def test_wal_append_entry(self, temp_wal_path):
        """Test appending entries to WAL."""
        with WriteAheadLog(temp_wal_path) as wal:
            data = {'operation': 'test', 'content': 'test data'}
            entry_id = wal.append('INSERT', data)
            
            assert entry_id is not None
            assert entry_id.startswith(str(int(time.time())))
            
            # Verify entry was written to file
            with open(temp_wal_path, 'r') as f:
                wal_data = json.load(f)
                assert len(wal_data) == 1
                assert wal_data[0]['operation'] == 'INSERT'
                assert wal_data[0]['data'] == data
                assert wal_data[0]['id'] == entry_id
    
    def test_wal_read_entries(self, temp_wal_path):
        """Test reading entries from WAL."""
        with WriteAheadLog(temp_wal_path) as wal:
            # Add multiple entries
            entries_data = [
                ('INSERT', {'key': 'value1'}),
                ('UPDATE', {'key': 'value2'}),
                ('DELETE', {'key': 'value3'})
            ]
            
            entry_ids = []
            for operation, data in entries_data:
                entry_id = wal.append(operation, data)
                entry_ids.append(entry_id)
            
            # Read all entries
            entries = wal.read_entries()
            assert len(entries) == 3
            
            for i, entry in enumerate(entries):
                assert entry.operation == entries_data[i][0]
                assert entry.data == entries_data[i][1]
                assert entry.id == entry_ids[i]
    
    def test_wal_read_entries_since_timestamp(self, temp_wal_path):
        """Test reading entries since specific timestamp."""
        with WriteAheadLog(temp_wal_path) as wal:
            # Add first entry
            wal.append('INSERT', {'key': 'old_value'})
            
            # Wait a bit and record timestamp
            time.sleep(0.1)
            since_timestamp = time.time()
            time.sleep(0.1)
            
            # Add second entry
            wal.append('UPDATE', {'key': 'new_value'})
            
            # Read entries since timestamp
            recent_entries = wal.read_entries(since_timestamp=since_timestamp)
            assert len(recent_entries) == 1
            assert recent_entries[0].operation == 'UPDATE'
            assert recent_entries[0].data == {'key': 'new_value'}
    
    def test_wal_truncate(self, temp_wal_path):
        """Test WAL truncation."""
        with WriteAheadLog(temp_wal_path) as wal:
            # Add entries with different timestamps
            old_timestamp = time.time() - 100
            new_timestamp = time.time()
            
            # Manually create entries with specific timestamps
            old_entry = WALEntry('INSERT', {'key': 'old'}, old_timestamp)
            new_entry = WALEntry('INSERT', {'key': 'new'}, new_timestamp)
            
            # Write entries directly to file
            wal_data = [old_entry.to_dict(), new_entry.to_dict()]
            with open(temp_wal_path, 'w') as f:
                json.dump(wal_data, f)
            
            # Truncate entries before current time
            truncate_timestamp = time.time() - 50
            removed_count = wal.truncate(truncate_timestamp)
            
            assert removed_count == 1
            
            # Verify only new entry remains
            entries = wal.read_entries()
            assert len(entries) == 1
            assert entries[0].data == {'key': 'new'}
    
    def test_wal_concurrent_append(self, temp_wal_path):
        """Test concurrent WAL append operations."""
        results = []
        errors = []
        
        def append_entry(index):
            try:
                with WriteAheadLog(temp_wal_path) as wal:
                    data = {'index': index, 'content': f'data_{index}'}
                    entry_id = wal.append('INSERT', data)
                    results.append(entry_id)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=append_entry, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert len(set(results)) == 10  # All IDs should be unique
        
        # Verify all entries were written
        with WriteAheadLog(temp_wal_path) as wal:
            entries = wal.read_entries()
            assert len(entries) == 10
    
    def test_wal_file_corruption_handling(self, temp_wal_path):
        """Test WAL handling of file corruption."""
        # Create WAL and add an entry
        with WriteAheadLog(temp_wal_path) as wal:
            wal.append('INSERT', {'key': 'value'})
        
        # Corrupt the WAL file
        with open(temp_wal_path, 'w') as f:
            f.write('invalid json content')
        
        # Try to read from corrupted WAL
        with WriteAheadLog(temp_wal_path) as wal:
            with pytest.raises(WALError):
                wal.read_entries()
    
    def test_wal_background_maintenance(self, temp_wal_path):
        """Test WAL background maintenance."""
        # Use short flush interval for testing
        with WriteAheadLog(temp_wal_path, flush_interval=0.1) as wal:
            # Add old entries
            old_timestamp = time.time() - (8 * 24 * 3600)  # 8 days ago
            old_entry = WALEntry('INSERT', {'key': 'old'}, old_timestamp)
            
            # Write old entry directly
            with open(temp_wal_path, 'w') as f:
                json.dump([old_entry.to_dict()], f)
            
            # Add new entry
            wal.append('INSERT', {'key': 'new'})
            
            # Wait for background maintenance
            time.sleep(0.2)
            
            # Old entries should be removed
            entries = wal.read_entries()
            assert len(entries) == 1
            assert entries[0].data == {'key': 'new'}
    
    def test_wal_flush(self, temp_wal_path):
        """Test WAL flush operation."""
        with WriteAheadLog(temp_wal_path) as wal:
            wal.append('INSERT', {'key': 'value'})
            
            # Flush should not raise an error
            wal.flush()
    
    def test_wal_context_manager(self, temp_wal_path):
        """Test WAL context manager functionality."""
        wal = None
        
        with WriteAheadLog(temp_wal_path) as wal:
            assert wal is not None
            wal.append('INSERT', {'key': 'value'})
        
        # WAL should be closed after context exit
        # Background thread should be stopped
        assert hasattr(wal, '_stop_flush')
    
    @patch('jojiai.wal.time.sleep')
    def test_wal_background_thread_error_handling(self, mock_sleep, temp_wal_path):
        """Test WAL background thread error handling."""
        # Mock sleep to avoid actual waiting
        mock_sleep.return_value = None
        
        with patch.object(WriteAheadLog, 'truncate') as mock_truncate:
            # Make truncate raise an error
            mock_truncate.side_effect = Exception("Test error")
            
            with WriteAheadLog(temp_wal_path, flush_interval=0.01) as wal:
                # Add an entry to trigger background processing
                wal.append('INSERT', {'key': 'value'})
                
                # Wait briefly for background thread
                time.sleep(0.05)
                
                # Background thread should handle the error gracefully
                # WAL should still be functional
                entry_id = wal.append('INSERT', {'key': 'value2'})
                assert entry_id is not None
    
    def test_wal_large_entry_handling(self, temp_wal_path):
        """Test WAL handling of large entries."""
        with WriteAheadLog(temp_wal_path) as wal:
            # Create large data
            large_data = {'content': 'x' * 100000}  # 100KB of data
            
            entry_id = wal.append('INSERT', large_data)
            assert entry_id is not None
            
            # Verify large entry can be read back
            entries = wal.read_entries()
            assert len(entries) == 1
            assert len(entries[0].data['content']) == 100000
    
    def test_wal_empty_data_handling(self, temp_wal_path):
        """Test WAL handling of empty data."""
        with WriteAheadLog(temp_wal_path) as wal:
            # Empty dictionary
            entry_id = wal.append('INSERT', {})
            assert entry_id is not None
            
            # Verify empty data can be read back
            entries = wal.read_entries()
            assert len(entries) == 1
            assert entries[0].data == {}
