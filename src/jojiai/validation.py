
"""Data validation utilities for JOJI Oi system."""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from .exceptions import ValidationError, InvalidSegment

logger = logging.getLogger(__name__)


def validate_segment(segment: Dict[str, Any]) -> bool:
    """Validate memory segment structure and content.
    
    Args:
        segment: Memory segment to validate
        
    Returns:
        True if segment is valid
        
    Raises:
        InvalidSegment: If segment is invalid
    """
    if not isinstance(segment, dict):
        raise InvalidSegment("Segment must be a dictionary")
    
    # Required fields
    required_fields = ['id', 'content', 'timestamp', 'type']
    missing_fields = [field for field in required_fields if field not in segment]
    if missing_fields:
        raise InvalidSegment(f"Missing required fields: {missing_fields}")
    
    # Validate field types
    if not isinstance(segment['id'], str) or not segment['id'].strip():
        raise InvalidSegment("Segment ID must be a non-empty string")
    
    if not isinstance(segment['content'], str):
        raise InvalidSegment("Segment content must be a string")
    
    if not isinstance(segment['timestamp'], (int, float)):
        raise InvalidSegment("Segment timestamp must be a number")
    
    if not isinstance(segment['type'], str) or segment['type'] not in ['dialogue', 'decision', 'profile', 'project']:
        raise InvalidSegment("Segment type must be one of: dialogue, decision, profile, project")
    
    # Validate content length
    if len(segment['content']) > 10000:  # 10KB limit
        raise InvalidSegment("Segment content exceeds maximum length (10KB)")
    
    # Validate timestamp range
    import time
    current_time = time.time()
    if segment['timestamp'] < 0 or segment['timestamp'] > current_time + 86400:  # Allow 1 day future
        raise InvalidSegment("Segment timestamp is out of valid range")
    
    logger.debug(f"Validated segment: {segment['id']}")
    return True


def validate_json_data(data: str) -> Dict[str, Any]:
    """Validate and parse JSON data.
    
    Args:
        data: JSON string to validate
        
    Returns:
        Parsed JSON data
        
    Raises:
        ValidationError: If JSON is invalid
    """
    if not isinstance(data, str):
        raise ValidationError("JSON data must be a string")
    
    if not data.strip():
        raise ValidationError("JSON data cannot be empty")
    
    try:
        parsed_data = json.loads(data)
        return parsed_data
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON data: {e}")


def validate_file_path(file_path: str) -> bool:
    """Validate file path for security and correctness.
    
    Args:
        file_path: File path to validate
        
    Returns:
        True if path is valid
        
    Raises:
        ValidationError: If path is invalid
    """
    if not isinstance(file_path, str):
        raise ValidationError("File path must be a string")
    
    if not file_path.strip():
        raise ValidationError("File path cannot be empty")
    
    # Check for path traversal attempts
    if '..' in file_path or file_path.startswith('/'):
        raise ValidationError("File path contains invalid characters")
    
    # Check file extension
    allowed_extensions = ['.json', '.md', '.txt', '.log']
    if not any(file_path.endswith(ext) for ext in allowed_extensions):
        raise ValidationError(f"File extension not allowed. Allowed: {allowed_extensions}")
    
    return True


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate system configuration.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        True if configuration is valid
        
    Raises:
        ValidationError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ValidationError("Configuration must be a dictionary")
    
    # Validate required configuration keys
    required_keys = ['memory_path', 'backup_path', 'wal_path']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValidationError(f"Missing required configuration keys: {missing_keys}")
    
    # Validate path configurations
    for key in required_keys:
        validate_file_path(config[key])
    
    # Validate optional numeric configurations
    numeric_configs = {
        'max_memory_size': (1000, 1000000),  # 1KB to 1MB
        'backup_interval': (60, 86400),      # 1 minute to 1 day
        'wal_flush_interval': (1, 300),      # 1 second to 5 minutes
        'lock_timeout': (1, 300),            # 1 second to 5 minutes
    }
    
    for key, (min_val, max_val) in numeric_configs.items():
        if key in config:
            value = config[key]
            if not isinstance(value, (int, float)):
                raise ValidationError(f"Configuration {key} must be a number")
            if not (min_val <= value <= max_val):
                raise ValidationError(f"Configuration {key} must be between {min_val} and {max_val}")
    
    logger.debug("Configuration validation passed")
    return True


def sanitize_input(data: Any) -> Any:
    """Sanitize input data to prevent injection attacks.
    
    Args:
        data: Input data to sanitize
        
    Returns:
        Sanitized data
    """
    if isinstance(data, str):
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '&', '"', "'", '\x00']
        sanitized = data
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        return sanitized.strip()
    
    elif isinstance(data, dict):
        return {key: sanitize_input(value) for key, value in data.items()}
    
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    
    else:
        return data
