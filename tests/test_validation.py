
"""Tests for validation utilities."""

import json
import pytest
import time
from jojiai.validation import (
    validate_segment, validate_json_data, validate_file_path,
    validate_config, sanitize_input
)
from jojiai.exceptions import ValidationError, InvalidSegment


class TestValidateSegment:
    """Test suite for validate_segment function."""
    
    def test_valid_segment(self):
        """Test validation of valid segment."""
        segment = {
            'id': 'test_segment_123',
            'content': 'This is test content',
            'timestamp': time.time(),
            'type': 'dialogue'
        }
        
        assert validate_segment(segment) is True
    
    def test_invalid_segment_type(self):
        """Test validation with invalid segment type."""
        with pytest.raises(InvalidSegment, match="Segment must be a dictionary"):
            validate_segment("not a dict")
        
        with pytest.raises(InvalidSegment, match="Segment must be a dictionary"):
            validate_segment(None)
        
        with pytest.raises(InvalidSegment, match="Segment must be a dictionary"):
            validate_segment([1, 2, 3])
    
    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        # Missing all fields
        with pytest.raises(InvalidSegment, match="Missing required fields"):
            validate_segment({})
        
        # Missing some fields
        segment = {
            'id': 'test_id',
            'content': 'test content'
            # Missing timestamp and type
        }
        with pytest.raises(InvalidSegment, match="Missing required fields"):
            validate_segment(segment)
    
    def test_invalid_field_types(self):
        """Test validation with invalid field types."""
        base_segment = {
            'id': 'test_id',
            'content': 'test content',
            'timestamp': time.time(),
            'type': 'dialogue'
        }
        
        # Invalid ID type
        segment = base_segment.copy()
        segment['id'] = 123
        with pytest.raises(InvalidSegment, match="Segment ID must be a non-empty string"):
            validate_segment(segment)
        
        # Empty ID
        segment = base_segment.copy()
        segment['id'] = ''
        with pytest.raises(InvalidSegment, match="Segment ID must be a non-empty string"):
            validate_segment(segment)
        
        # Invalid content type
        segment = base_segment.copy()
        segment['content'] = 123
        with pytest.raises(InvalidSegment, match="Segment content must be a string"):
            validate_segment(segment)
        
        # Invalid timestamp type
        segment = base_segment.copy()
        segment['timestamp'] = 'not a number'
        with pytest.raises(InvalidSegment, match="Segment timestamp must be a number"):
            validate_segment(segment)
        
        # Invalid type
        segment = base_segment.copy()
        segment['type'] = 'invalid_type'
        with pytest.raises(InvalidSegment, match="Segment type must be one of"):
            validate_segment(segment)
    
    def test_content_size_limit(self):
        """Test content size validation."""
        base_segment = {
            'id': 'test_id',
            'content': 'x' * 10001,  # Over 10KB limit
            'timestamp': time.time(),
            'type': 'dialogue'
        }
        
        with pytest.raises(InvalidSegment, match="Segment content exceeds maximum length"):
            validate_segment(base_segment)
        
        # Test at the limit
        base_segment['content'] = 'x' * 10000  # Exactly 10KB
        assert validate_segment(base_segment) is True
    
    def test_timestamp_range_validation(self):
        """Test timestamp range validation."""
        base_segment = {
            'id': 'test_id',
            'content': 'test content',
            'timestamp': -1,  # Negative timestamp
            'type': 'dialogue'
        }
        
        with pytest.raises(InvalidSegment, match="Segment timestamp is out of valid range"):
            validate_segment(base_segment)
        
        # Future timestamp (more than 1 day)
        base_segment['timestamp'] = time.time() + 100000
        with pytest.raises(InvalidSegment, match="Segment timestamp is out of valid range"):
            validate_segment(base_segment)
        
        # Valid future timestamp (within 1 day)
        base_segment['timestamp'] = time.time() + 3600  # 1 hour future
        assert validate_segment(base_segment) is True
    
    def test_valid_segment_types(self):
        """Test all valid segment types."""
        valid_types = ['dialogue', 'decision', 'profile', 'project']
        
        for segment_type in valid_types:
            segment = {
                'id': f'test_{segment_type}',
                'content': f'Test {segment_type} content',
                'timestamp': time.time(),
                'type': segment_type
            }
            assert validate_segment(segment) is True


class TestValidateJsonData:
    """Test suite for validate_json_data function."""
    
    def test_valid_json(self):
        """Test validation of valid JSON."""
        valid_json = '{"key": "value", "number": 123, "array": [1, 2, 3]}'
        result = validate_json_data(valid_json)
        
        assert isinstance(result, dict)
        assert result['key'] == 'value'
        assert result['number'] == 123
        assert result['array'] == [1, 2, 3]
    
    def test_invalid_json_type(self):
        """Test validation with invalid input type."""
        with pytest.raises(ValidationError, match="JSON data must be a string"):
            validate_json_data(123)
        
        with pytest.raises(ValidationError, match="JSON data must be a string"):
            validate_json_data(None)
        
        with pytest.raises(ValidationError, match="JSON data must be a string"):
            validate_json_data(['not', 'a', 'string'])
    
    def test_empty_json(self):
        """Test validation with empty JSON."""
        with pytest.raises(ValidationError, match="JSON data cannot be empty"):
            validate_json_data('')
        
        with pytest.raises(ValidationError, match="JSON data cannot be empty"):
            validate_json_data('   ')
    
    def test_malformed_json(self):
        """Test validation with malformed JSON."""
        malformed_json_cases = [
            '{"key": "value"',  # Missing closing brace
            '{"key": value}',   # Unquoted value
            '{key: "value"}',   # Unquoted key
            '{"key": "value",}',  # Trailing comma
            'not json at all'
        ]
        
        for malformed_json in malformed_json_cases:
            with pytest.raises(ValidationError, match="Invalid JSON data"):
                validate_json_data(malformed_json)


class TestValidateFilePath:
    """Test suite for validate_file_path function."""
    
    def test_valid_file_paths(self):
        """Test validation of valid file paths."""
        valid_paths = [
            'data.json',
            'folder/data.json',
            'deep/folder/structure/file.md',
            'config.txt',
            'logs/app.log'
        ]
        
        for path in valid_paths:
            assert validate_file_path(path) is True
    
    def test_invalid_file_path_type(self):
        """Test validation with invalid path type."""
        with pytest.raises(ValidationError, match="File path must be a string"):
            validate_file_path(123)
        
        with pytest.raises(ValidationError, match="File path must be a string"):
            validate_file_path(None)
    
    def test_empty_file_path(self):
        """Test validation with empty path."""
        with pytest.raises(ValidationError, match="File path cannot be empty"):
            validate_file_path('')
        
        with pytest.raises(ValidationError, match="File path cannot be empty"):
            validate_file_path('   ')
    
    def test_path_traversal_attempts(self):
        """Test validation against path traversal."""
        dangerous_paths = [
            '../config.json',
            'folder/../../../etc/passwd',
            '/absolute/path/file.json',
            'folder/../../file.json'
        ]
        
        for path in dangerous_paths:
            with pytest.raises(ValidationError, match="File path contains invalid characters"):
                validate_file_path(path)
    
    def test_invalid_file_extensions(self):
        """Test validation of file extensions."""
        invalid_extensions = [
            'file.exe',
            'script.sh',
            'data.bin',
            'config.ini',
            'file'  # No extension
        ]
        
        for path in invalid_extensions:
            with pytest.raises(ValidationError, match="File extension not allowed"):
                validate_file_path(path)


class TestValidateConfig:
    """Test suite for validate_config function."""
    
    def test_valid_config(self):
        """Test validation of valid configuration."""
        config = {
            'memory_path': 'data/memory.json',
            'backup_path': 'backups/backup.json',
            'wal_path': 'logs/wal.log',
            'max_memory_size': 50000,
            'backup_interval': 3600,
            'wal_flush_interval': 60,
            'lock_timeout': 30
        }
        
        assert validate_config(config) is True
    
    def test_invalid_config_type(self):
        """Test validation with invalid config type."""
        with pytest.raises(ValidationError, match="Configuration must be a dictionary"):
            validate_config("not a dict")
        
        with pytest.raises(ValidationError, match="Configuration must be a dictionary"):
            validate_config(None)
    
    def test_missing_required_keys(self):
        """Test validation with missing required keys."""
        incomplete_configs = [
            {},  # Missing all keys
            {'memory_path': 'data.json'},  # Missing backup_path and wal_path
            {'memory_path': 'data.json', 'backup_path': 'backup.json'}  # Missing wal_path
        ]
        
        for config in incomplete_configs:
            with pytest.raises(ValidationError, match="Missing required configuration keys"):
                validate_config(config)
    
    def test_invalid_numeric_configs(self):
        """Test validation of numeric configuration values."""
        base_config = {
            'memory_path': 'data.json',
            'backup_path': 'backup.json',
            'wal_path': 'wal.log'
        }
        
        # Test invalid types
        config = base_config.copy()
        config['max_memory_size'] = 'not a number'
        with pytest.raises(ValidationError, match="Configuration max_memory_size must be a number"):
            validate_config(config)
        
        # Test out of range values
        config = base_config.copy()
        config['max_memory_size'] = 500  # Below minimum
        with pytest.raises(ValidationError, match="Configuration max_memory_size must be between"):
            validate_config(config)
        
        config = base_config.copy()
        config['backup_interval'] = 30  # Below minimum
        with pytest.raises(ValidationError, match="Configuration backup_interval must be between"):
            validate_config(config)


class TestSanitizeInput:
    """Test suite for sanitize_input function."""
    
    def test_sanitize_string(self):
        """Test string sanitization."""
        dangerous_string = '<script>alert("xss")</script>'
        sanitized = sanitize_input(dangerous_string)
        
        assert '<' not in sanitized
        assert '>' not in sanitized
        assert 'script' in sanitized  # Content should remain, just tags removed
    
    def test_sanitize_dict(self):
        """Test dictionary sanitization."""
        dangerous_dict = {
            'safe_key': 'safe_value',
            'dangerous_key': '<script>alert("xss")</script>',
            'nested': {
                'inner_dangerous': '&lt;malicious&gt;'
            }
        }
        
        sanitized = sanitize_input(dangerous_dict)
        
        assert sanitized['safe_key'] == 'safe_value'
        assert '<script>' not in sanitized['dangerous_key']
        assert '&lt;' not in sanitized['nested']['inner_dangerous']
    
    def test_sanitize_list(self):
        """Test list sanitization."""
        dangerous_list = [
            'safe_item',
            '<script>alert("xss")</script>',
            {'nested_dangerous': '&quot;malicious&quot;'}
        ]
        
        sanitized = sanitize_input(dangerous_list)
        
        assert sanitized[0] == 'safe_item'
        assert '<script>' not in sanitized[1]
        assert '&quot;' not in sanitized[2]['nested_dangerous']
    
    def test_sanitize_non_string_types(self):
        """Test sanitization of non-string types."""
        # Numbers should pass through unchanged
        assert sanitize_input(123) == 123
        assert sanitize_input(45.67) == 45.67
        
        # Booleans should pass through unchanged
        assert sanitize_input(True) is True
        assert sanitize_input(False) is False
        
        # None should pass through unchanged
        assert sanitize_input(None) is None
    
    def test_sanitize_whitespace_handling(self):
        """Test whitespace handling in sanitization."""
        input_with_whitespace = '  <script>  dangerous content  </script>  '
        sanitized = sanitize_input(input_with_whitespace)
        
        # Should strip whitespace and remove dangerous characters
        assert sanitized == 'dangerous content'
        assert not sanitized.startswith(' ')
        assert not sanitized.endswith(' ')
    
    def test_sanitize_null_bytes(self):
        """Test removal of null bytes."""
        dangerous_string = 'content\x00with\x00null\x00bytes'
        sanitized = sanitize_input(dangerous_string)
        
        assert '\x00' not in sanitized
        assert sanitized == 'contentwithullbytes'
    
    def test_sanitize_complex_nested_structure(self):
        """Test sanitization of complex nested structures."""
        complex_structure = {
            'level1': {
                'level2': [
                    'safe_string',
                    '<dangerous>content</dangerous>',
                    {
                        'level3': '&quot;nested&quot; <script>alert()</script>'
                    }
                ]
            },
            'simple_list': ['item1', '<item2>', 'item3'],
            'safe_data': 'normal content'
        }
        
        sanitized = sanitize_input(complex_structure)
        
        # Check deep sanitization
        assert '<dangerous>' not in sanitized['level1']['level2'][1]
        assert 'content' in sanitized['level1']['level2'][1]
        assert '&quot;' not in sanitized['level1']['level2'][2]['level3']
        assert '<script>' not in sanitized['level1']['level2'][2]['level3']
        assert '<item2>' not in sanitized['simple_list'][1]
        assert sanitized['safe_data'] == 'normal content'
