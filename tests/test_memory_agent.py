
"""Tests for MemoryAgent with race condition fixes."""

import json
import time
import pytest
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

from jojiai.memory_agent import MemoryAgent
from jojiai.exceptions import MemoryError, InvalidSegment, ConcurrencyError


class TestMemoryAgent:
    """Test suite for MemoryAgent."""
    
    @pytest.fixture
    def temp_memory_path(self):
        """Create temporary memory path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def memory_agent(self, temp_memory_path):
        """Create MemoryAgent instance."""
        config = {
            'max_dialogues': 100,
            'max_decisions': 50
        }
        with MemoryAgent(temp_memory_path, config) as agent:
            yield agent
    
    def test_initialization(self, temp_memory_path):
        """Test MemoryAgent initialization."""
        with MemoryAgent(temp_memory_path) as agent:
            assert agent.memory_path.exists()
            assert agent.dialogues_file.exists()
            assert agent.decisions_file.exists()
            assert agent.profile_file.exists()
            assert agent.projects_file.exists()
            assert agent.lock_dir.exists()
    
    def test_store_dialogue_success(self, memory_agent):
        """Test successful dialogue storage."""
        dialogue = {
            'role': 'user',
            'content': 'Hello, world!',
            'metadata': {'test': True}
        }
        
        dialogue_id = memory_agent.store_dialogue(dialogue)
        assert dialogue_id.startswith('dialogue_')
        
        # Verify storage
        dialogues = memory_agent.get_dialogues()
        assert len(dialogues) == 1
        assert dialogues[0]['id'] == dialogue_id
    
    def test_store_dialogue_validation(self, memory_agent):
        """Test dialogue validation."""
        # Test invalid dialogue (missing content)
        with pytest.raises(InvalidSegment):
            memory_agent.store_dialogue({})
        
        # Test dialogue with malicious content
        dialogue = {
            'role': 'user',
            'content': '<script>alert("xss")</script>',
            'metadata': {}
        }
        
        dialogue_id = memory_agent.store_dialogue(dialogue)
        dialogues = memory_agent.get_dialogues()
        stored_content = json.loads(dialogues[0]['content'])
        
        # Content should be sanitized
        assert '<script>' not in stored_content['content']
    
    def test_store_decision_success(self, memory_agent):
        """Test successful decision storage."""
        decision = {
            'action': 'test_action',
            'reasoning': 'Test reasoning',
            'confidence': 0.95
        }
        
        decision_id = memory_agent.store_decision(decision)
        assert decision_id.startswith('decision_')
        
        # Verify storage
        decisions = memory_agent.get_decisions()
        assert len(decisions) == 1
        assert decisions[0]['id'] == decision_id
    
    def test_update_profile_success(self, memory_agent):
        """Test successful profile update."""
        profile_data = {
            'name': 'Test User',
            'preferences': {'theme': 'dark'},
            'settings': {'notifications': True}
        }
        
        memory_agent.update_profile(profile_data)
        
        # Verify update
        profile = memory_agent.get_profile()
        assert profile['name'] == 'Test User'
        assert profile['preferences']['theme'] == 'dark'
        assert 'last_updated' in profile
    
    def test_concurrent_dialogue_storage(self, memory_agent):
        """Test concurrent dialogue storage without race conditions."""
        results = []
        errors = []
        
        def store_dialogue(index):
            try:
                dialogue = {
                    'role': 'user',
                    'content': f'Message {index}',
                    'metadata': {'index': index}
                }
                dialogue_id = memory_agent.store_dialogue(dialogue)
                results.append(dialogue_id)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=store_dialogue, args=(i,))
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
        
        # Verify all dialogues were stored
        dialogues = memory_agent.get_dialogues()
        assert len(dialogues) == 10
    
    def test_concurrent_profile_updates(self, memory_agent):
        """Test concurrent profile updates without race conditions."""
        errors = []
        
        def update_profile(index):
            try:
                profile_data = {f'key_{index}': f'value_{index}'}
                memory_agent.update_profile(profile_data)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_profile, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # Verify all updates were applied
        profile = memory_agent.get_profile()
        for i in range(5):
            assert f'key_{i}' in profile
            assert profile[f'key_{i}'] == f'value_{i}'
    
    def test_memory_limits(self, temp_memory_path):
        """Test memory size limits."""
        config = {
            'max_dialogues': 3,
            'max_decisions': 2
        }
        
        with MemoryAgent(temp_memory_path, config) as agent:
            # Store more dialogues than limit
            for i in range(5):
                dialogue = {
                    'role': 'user',
                    'content': f'Message {i}',
                    'metadata': {}
                }
                agent.store_dialogue(dialogue)
            
            # Should only keep the last 3
            dialogues = agent.get_dialogues()
            assert len(dialogues) == 3
            
            # Store more decisions than limit
            for i in range(4):
                decision = {
                    'action': f'action_{i}',
                    'reasoning': f'reasoning_{i}'
                }
                agent.store_decision(decision)
            
            # Should only keep the last 2
            decisions = agent.get_decisions()
            assert len(decisions) == 2
    
    def test_wal_integration(self, memory_agent):
        """Test WAL integration."""
        dialogue = {
            'role': 'user',
            'content': 'Test message',
            'metadata': {}
        }
        
        # Store dialogue
        dialogue_id = memory_agent.store_dialogue(dialogue)
        
        # Check WAL entries
        wal_entries = memory_agent.wal.read_entries()
        assert len(wal_entries) > 0
        
        # Find the dialogue entry
        dialogue_entry = None
        for entry in wal_entries:
            if entry.operation == 'INSERT' and 'memory_dialogues_v2.json' in entry.data.get('file', ''):
                dialogue_entry = entry
                break
        
        assert dialogue_entry is not None
        assert dialogue_entry.data['content']['id'] == dialogue_id
    
    def test_backup_integration(self, memory_agent):
        """Test backup integration."""
        # Store some data
        dialogue = {
            'role': 'user',
            'content': 'Test message',
            'metadata': {}
        }
        memory_agent.store_dialogue(dialogue)
        
        # Create snapshot
        snapshot_id = memory_agent.create_snapshot('test_snapshot')
        assert snapshot_id == 'test_snapshot'
        
        # Verify snapshot exists
        snapshots = memory_agent.backup_manager.list_snapshots()
        assert len(snapshots) > 0
        assert any(s['snapshot_name'] == 'test_snapshot' for s in snapshots)
    
    def test_memory_stats(self, memory_agent):
        """Test memory statistics."""
        # Store some data
        dialogue = {'role': 'user', 'content': 'Test', 'metadata': {}}
        decision = {'action': 'test', 'reasoning': 'test'}
        profile = {'name': 'Test User'}
        
        memory_agent.store_dialogue(dialogue)
        memory_agent.store_decision(decision)
        memory_agent.update_profile(profile)
        
        # Get stats
        stats = memory_agent.get_memory_stats()
        
        assert stats['dialogues_count'] == 1
        assert stats['decisions_count'] == 1
        assert stats['profile_keys'] > 0
        assert 'memory_path' in stats
        assert 'wal_entries' in stats
        assert 'snapshots' in stats
    
    def test_file_corruption_recovery(self, temp_memory_path):
        """Test recovery from file corruption."""
        with MemoryAgent(temp_memory_path) as agent:
            # Store some data
            dialogue = {'role': 'user', 'content': 'Test', 'metadata': {}}
            agent.store_dialogue(dialogue)
        
        # Corrupt the dialogues file
        dialogues_file = Path(temp_memory_path) / 'memory_dialogues_v2.json'
        with open(dialogues_file, 'w') as f:
            f.write('invalid json content')
        
        # Try to read - should handle corruption gracefully
        with MemoryAgent(temp_memory_path) as agent:
            with pytest.raises(MemoryError):
                agent.get_dialogues()
    
    @patch('jojiai.file_lock.fcntl.flock')
    def test_lock_timeout(self, mock_flock, temp_memory_path):
        """Test file lock timeout handling."""
        # Mock flock to raise EAGAIN (lock unavailable)
        import errno
        mock_flock.side_effect = OSError(errno.EAGAIN, "Resource temporarily unavailable")
        
        with MemoryAgent(temp_memory_path) as agent:
            dialogue = {'role': 'user', 'content': 'Test', 'metadata': {}}
            
            with pytest.raises(ConcurrencyError):
                agent.store_dialogue(dialogue)
    
    def test_large_content_handling(self, memory_agent):
        """Test handling of large content."""
        # Test content at the limit
        large_content = 'x' * 9999  # Just under 10KB limit
        dialogue = {
            'role': 'user',
            'content': large_content,
            'metadata': {}
        }
        
        dialogue_id = memory_agent.store_dialogue(dialogue)
        assert dialogue_id is not None
        
        # Test content over the limit
        too_large_content = 'x' * 10001  # Over 10KB limit
        dialogue = {
            'role': 'user',
            'content': too_large_content,
            'metadata': {}
        }
        
        with pytest.raises(InvalidSegment):
            memory_agent.store_dialogue(dialogue)
    
    def test_timestamp_validation(self, memory_agent):
        """Test timestamp validation."""
        # Test future timestamp (should be rejected)
        future_time = time.time() + 100000  # Far future
        
        with patch('time.time', return_value=future_time):
            dialogue = {
                'role': 'user',
                'content': 'Test message',
                'metadata': {}
            }
            
            with pytest.raises(InvalidSegment):
                memory_agent.store_dialogue(dialogue)
    
    def test_context_manager(self, temp_memory_path):
        """Test context manager functionality."""
        agent = None
        
        with MemoryAgent(temp_memory_path) as agent:
            assert agent is not None
            dialogue = {'role': 'user', 'content': 'Test', 'metadata': {}}
            agent.store_dialogue(dialogue)
        
        # Agent should be closed after context exit
        # WAL and backup manager should be closed
        assert hasattr(agent, 'wal')
        assert hasattr(agent, 'backup_manager')


class TestMemoryAgentEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def temp_memory_path(self):
        """Create temporary memory path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_invalid_memory_path(self):
        """Test invalid memory path handling."""
        # Test with read-only path
        with tempfile.TemporaryDirectory() as temp_dir:
            readonly_path = Path(temp_dir) / 'readonly'
            readonly_path.mkdir()
            readonly_path.chmod(0o444)  # Read-only
            
            try:
                with pytest.raises((PermissionError, OSError)):
                    MemoryAgent(str(readonly_path))
            finally:
                readonly_path.chmod(0o755)  # Restore permissions for cleanup
    
    def test_empty_dialogue_content(self, temp_memory_path):
        """Test empty dialogue content handling."""
        with MemoryAgent(temp_memory_path) as agent:
            dialogue = {
                'role': 'user',
                'content': '',
                'metadata': {}
            }
            
            with pytest.raises(InvalidSegment):
                agent.store_dialogue(dialogue)
    
    def test_none_values_handling(self, temp_memory_path):
        """Test None values handling."""
        with MemoryAgent(temp_memory_path) as agent:
            # Test None dialogue
            with pytest.raises(InvalidSegment):
                agent.store_dialogue(None)
            
            # Test None decision
            with pytest.raises(InvalidSegment):
                agent.store_decision(None)
            
            # Test None profile update
            with pytest.raises(InvalidSegment):
                agent.update_profile(None)
    
    def test_malformed_json_recovery(self, temp_memory_path):
        """Test recovery from malformed JSON files."""
        # Create agent and store some data
        with MemoryAgent(temp_memory_path) as agent:
            dialogue = {'role': 'user', 'content': 'Test', 'metadata': {}}
            agent.store_dialogue(dialogue)
        
        # Corrupt the file with malformed JSON
        dialogues_file = Path(temp_memory_path) / 'memory_dialogues_v2.json'
        with open(dialogues_file, 'w') as f:
            f.write('[{"incomplete": "json"')
        
        # Try to create new agent - should handle corruption
        with MemoryAgent(temp_memory_path) as agent:
            # Should be able to store new data despite corruption
            new_dialogue = {'role': 'user', 'content': 'New test', 'metadata': {}}
            with pytest.raises(MemoryError):
                agent.store_dialogue(new_dialogue)
