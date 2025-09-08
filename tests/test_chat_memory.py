
"""Tests for ChatMemory component."""

import json
import time
import pytest
import tempfile
import threading
from pathlib import Path

from jojiai.chat_memory import ChatMemory
from jojiai.exceptions import MemoryError, InvalidSegment


class TestChatMemory:
    """Test suite for ChatMemory."""
    
    @pytest.fixture
    def temp_memory_path(self):
        """Create temporary memory path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def chat_memory(self, temp_memory_path):
        """Create ChatMemory instance."""
        config = {
            'max_buffer_size': 1000
        }
        with ChatMemory(temp_memory_path, config) as chat:
            yield chat
    
    def test_initialization(self, temp_memory_path):
        """Test ChatMemory initialization."""
        with ChatMemory(temp_memory_path) as chat:
            assert chat.memory_path.exists()
            assert chat.session_file.exists()
            assert chat.conversations_file.exists()
            assert chat.memory_agent is not None
    
    def test_add_message_success(self, chat_memory):
        """Test successful message addition."""
        message_id = chat_memory.add_message('user', 'Hello, world!')
        assert message_id.startswith('dialogue_')
        
        # Verify message was stored
        history = chat_memory.get_conversation_history()
        assert len(history) == 1
        assert history[0]['role'] == 'user'
        assert history[0]['content'] == 'Hello, world!'
    
    def test_add_message_with_metadata(self, chat_memory):
        """Test message addition with metadata."""
        metadata = {'source': 'test', 'priority': 'high'}
        message_id = chat_memory.add_message('assistant', 'Hello back!', metadata)
        
        history = chat_memory.get_conversation_history()
        assert len(history) == 1
        assert history[0]['metadata'] == metadata
    
    def test_add_message_validation(self, chat_memory):
        """Test message validation."""
        # Test invalid role
        with pytest.raises(InvalidSegment):
            chat_memory.add_message('invalid_role', 'Test message')
        
        # Test empty content
        with pytest.raises(InvalidSegment):
            chat_memory.add_message('user', '')
        
        # Test whitespace-only content
        with pytest.raises(InvalidSegment):
            chat_memory.add_message('user', '   ')
    
    def test_conversation_history(self, chat_memory):
        """Test conversation history retrieval."""
        # Add multiple messages
        messages = [
            ('user', 'First message'),
            ('assistant', 'First response'),
            ('user', 'Second message'),
            ('assistant', 'Second response')
        ]
        
        for role, content in messages:
            chat_memory.add_message(role, content)
        
        # Get full history
        history = chat_memory.get_conversation_history()
        assert len(history) == 4
        
        # Check order (should be chronological)
        assert history[0]['content'] == 'First message'
        assert history[-1]['content'] == 'Second response'
        
        # Test limit
        limited_history = chat_memory.get_conversation_history(limit=2)
        assert len(limited_history) == 2
        assert limited_history[0]['content'] == 'Second message'
        assert limited_history[1]['content'] == 'Second response'
    
    def test_role_filtering(self, chat_memory):
        """Test conversation history role filtering."""
        # Add messages with different roles
        chat_memory.add_message('user', 'User message 1')
        chat_memory.add_message('assistant', 'Assistant message 1')
        chat_memory.add_message('system', 'System message 1')
        chat_memory.add_message('user', 'User message 2')
        
        # Filter by user role
        user_messages = chat_memory.get_conversation_history(role_filter='user')
        assert len(user_messages) == 2
        assert all(msg['role'] == 'user' for msg in user_messages)
        
        # Filter by assistant role
        assistant_messages = chat_memory.get_conversation_history(role_filter='assistant')
        assert len(assistant_messages) == 1
        assert assistant_messages[0]['role'] == 'assistant'
    
    def test_context_window(self, chat_memory):
        """Test context window functionality."""
        # Add multiple messages
        for i in range(15):
            chat_memory.add_message('user', f'Message {i}')
        
        # Get context window
        context = chat_memory.get_context_window(window_size=5)
        assert len(context) == 5
        
        # Should be the most recent messages
        assert context[0]['content'] == 'Message 10'
        assert context[-1]['content'] == 'Message 14'
    
    def test_search_messages(self, chat_memory):
        """Test message search functionality."""
        # Add messages with searchable content
        messages = [
            ('user', 'I love Python programming'),
            ('assistant', 'Python is great for data science'),
            ('user', 'What about JavaScript?'),
            ('assistant', 'JavaScript is good for web development'),
            ('user', 'I prefer Python over JavaScript')
        ]
        
        for role, content in messages:
            chat_memory.add_message(role, content)
        
        # Search for Python
        python_results = chat_memory.search_messages('Python')
        assert len(python_results) == 3
        assert all('python' in msg['content'].lower() for msg in python_results)
        
        # Search for JavaScript
        js_results = chat_memory.search_messages('JavaScript')
        assert len(js_results) == 2
        
        # Search for non-existent term
        no_results = chat_memory.search_messages('nonexistent')
        assert len(no_results) == 0
    
    def test_conversation_summary(self, chat_memory):
        """Test conversation summary creation."""
        # Add some messages
        messages = [
            ('user', 'Hello'),
            ('assistant', 'Hi there!'),
            ('user', 'How are you?'),
            ('assistant', 'I am doing well, thank you!')
        ]
        
        for role, content in messages:
            chat_memory.add_message(role, content)
        
        # Create summary
        summary = chat_memory.create_conversation_summary()
        
        assert 'Conversation Summary' in summary
        assert '4 messages' in summary
        assert 'user: 2 messages' in summary
        assert 'assistant: 2 messages' in summary
        assert 'Recent messages:' in summary
    
    def test_session_buffer_update(self, chat_memory):
        """Test session buffer updates."""
        # Add a message
        chat_memory.add_message('user', 'Test message')
        
        # Check session buffer
        buffer_content = chat_memory.get_session_buffer()
        assert 'User (' in buffer_content
        assert 'Test message' in buffer_content
    
    def test_session_buffer_size_limit(self, temp_memory_path):
        """Test session buffer size limiting."""
        config = {'max_buffer_size': 200}  # Small buffer
        
        with ChatMemory(temp_memory_path, config) as chat:
            # Add many messages to exceed buffer size
            for i in range(10):
                chat.add_message('user', f'This is a long message number {i} with lots of content')
            
            buffer_content = chat.get_session_buffer()
            assert len(buffer_content) <= 250  # Should be limited
    
    def test_clear_session_buffer(self, chat_memory):
        """Test session buffer clearing."""
        # Add a message
        chat_memory.add_message('user', 'Test message')
        
        # Verify buffer has content
        buffer_content = chat_memory.get_session_buffer()
        assert 'Test message' in buffer_content
        
        # Clear buffer
        chat_memory.clear_session_buffer()
        
        # Verify buffer is cleared
        buffer_content = chat_memory.get_session_buffer()
        assert buffer_content == "# Chat Session Buffer\n\n"
    
    def test_concurrent_message_addition(self, chat_memory):
        """Test concurrent message addition."""
        results = []
        errors = []
        
        def add_message(index):
            try:
                message_id = chat_memory.add_message('user', f'Message {index}')
                results.append(message_id)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=add_message, args=(i,))
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
        
        # Verify all messages were stored
        history = chat_memory.get_conversation_history()
        assert len(history) == 10
    
    def test_chat_stats(self, chat_memory):
        """Test chat statistics."""
        # Add messages with different roles
        chat_memory.add_message('user', 'User message 1')
        chat_memory.add_message('assistant', 'Assistant message 1')
        chat_memory.add_message('system', 'System message 1')
        chat_memory.add_message('user', 'User message 2')
        
        # Get stats
        stats = chat_memory.get_chat_stats()
        
        assert stats['total_messages'] == 4
        assert stats['role_distribution']['user'] == 2
        assert stats['role_distribution']['assistant'] == 1
        assert stats['role_distribution']['system'] == 1
        assert 'time_span_seconds' in stats
        assert 'session_buffer_size' in stats
        assert 'memory_stats' in stats
    
    def test_malformed_dialogue_handling(self, temp_memory_path):
        """Test handling of malformed dialogue data."""
        with ChatMemory(temp_memory_path) as chat:
            # Add a normal message
            chat.add_message('user', 'Normal message')
            
            # Manually corrupt the dialogue data
            dialogues_file = chat.memory_path / 'memory_dialogues_v2.json'
            with open(dialogues_file, 'r') as f:
                data = json.load(f)
            
            # Add malformed entry
            data.append({
                'id': 'malformed',
                'content': 'not valid json',  # Should be JSON string
                'timestamp': time.time(),
                'type': 'dialogue'
            })
            
            with open(dialogues_file, 'w') as f:
                json.dump(data, f)
            
            # Should handle malformed data gracefully
            history = chat.get_conversation_history()
            assert len(history) == 1  # Only the valid message
            assert history[0]['content'] == 'Normal message'
    
    def test_empty_search_query(self, chat_memory):
        """Test search with empty query."""
        chat_memory.add_message('user', 'Test message')
        
        # Empty query should return no results
        results = chat_memory.search_messages('')
        assert len(results) == 0
        
        # Whitespace-only query should return no results
        results = chat_memory.search_messages('   ')
        assert len(results) == 0
    
    def test_context_manager(self, temp_memory_path):
        """Test context manager functionality."""
        chat = None
        
        with ChatMemory(temp_memory_path) as chat:
            assert chat is not None
            chat.add_message('user', 'Test message')
        
        # Chat should be closed after context exit
        assert hasattr(chat, 'memory_agent')


class TestChatMemoryEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def temp_memory_path(self):
        """Create temporary memory path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_large_message_content(self, temp_memory_path):
        """Test handling of large message content."""
        with ChatMemory(temp_memory_path) as chat:
            # Test message at size limit
            large_content = 'x' * 9999  # Just under limit
            message_id = chat.add_message('user', large_content)
            assert message_id is not None
            
            # Test message over size limit
            too_large_content = 'x' * 10001  # Over limit
            with pytest.raises(InvalidSegment):
                chat.add_message('user', too_large_content)
    
    def test_special_characters_in_content(self, temp_memory_path):
        """Test handling of special characters in message content."""
        with ChatMemory(temp_memory_path) as chat:
            special_content = "Message with special chars: <>&\"'\x00"
            message_id = chat.add_message('user', special_content)
            
            # Verify content was sanitized
            history = chat.get_conversation_history()
            assert len(history) == 1
            # Special characters should be removed or escaped
            stored_content = history[0]['content']
            assert '<' not in stored_content
            assert '>' not in stored_content
            assert '\x00' not in stored_content
    
    def test_unicode_content_handling(self, temp_memory_path):
        """Test handling of Unicode content."""
        with ChatMemory(temp_memory_path) as chat:
            unicode_content = "Message with Unicode: 你好 🌟 café naïve"
            message_id = chat.add_message('user', unicode_content)
            
            history = chat.get_conversation_history()
            assert len(history) == 1
            assert history[0]['content'] == unicode_content
    
    def test_no_conversation_history(self, temp_memory_path):
        """Test behavior with no conversation history."""
        with ChatMemory(temp_memory_path) as chat:
            # Get history when empty
            history = chat.get_conversation_history()
            assert len(history) == 0
            
            # Get context window when empty
            context = chat.get_context_window()
            assert len(context) == 0
            
            # Search when empty
            results = chat.search_messages('test')
            assert len(results) == 0
            
            # Create summary when empty
            summary = chat.create_conversation_summary()
            assert 'No conversation history available' in summary
