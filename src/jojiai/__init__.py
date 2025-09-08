
"""JOJI Oi - AI-powered memory system with comprehensive fixes."""

__version__ = "1.0.0"
__author__ = "JOJI Oi Development Team"
__email__ = "dev@jojiai.com"
__description__ = "AI-powered memory system with race condition fixes and comprehensive monitoring"

# Core components
from .core import JOJIAICore
from .memory_agent import MemoryAgent
from .chat_memory import ChatMemory

# Utilities
from .validation import validate_segment, validate_json_data, sanitize_input
from .file_lock import FileLock, atomic_write, with_retry
from .wal import WriteAheadLog, WALEntry
from .backup import BackupManager
from .monitoring import (
    StructuredLogger, MetricsCollector, monitor_operation,
    HealthChecker, AlertManager, metrics_collector, health_checker, alert_manager
)

# Exceptions
from .exceptions import (
    JOJIAIException, ValidationError, InvalidSegment, ConcurrencyError,
    FileOperationError, MemoryError, WALError, BackupError, RecoveryError
)

# Version info
VERSION_INFO = {
    'version': __version__,
    'components': [
        'MemoryAgent',
        'ChatMemory', 
        'WriteAheadLog',
        'BackupManager',
        'Monitoring',
        'FileLock'
    ],
    'features': [
        'Race condition fixes',
        'Atomic file operations',
        'Write-ahead logging',
        'Automated backups',
        'Prometheus metrics',
        'Structured logging',
        'Health monitoring',
        'CLI management tools'
    ]
}

def get_version():
    """Get version information."""
    return VERSION_INFO

def health_check():
    """Perform basic health check."""
    try:
        # Test core components
        from .validation import validate_segment
        from .file_lock import FileLock
        from .monitoring import metrics_collector
        
        # Basic validation test
        test_segment = {
            'id': 'health_check',
            'content': 'test',
            'timestamp': 1694123456.0,
            'type': 'dialogue'
        }
        validate_segment(test_segment)
        
        return {
            'status': 'healthy',
            'version': __version__,
            'components': 'all_loaded'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'version': __version__
        }

# Export all public components
__all__ = [
    # Core
    'JOJIAICore',
    'MemoryAgent', 
    'ChatMemory',
    
    # Utilities
    'validate_segment',
    'validate_json_data', 
    'sanitize_input',
    'FileLock',
    'atomic_write',
    'with_retry',
    'WriteAheadLog',
    'WALEntry',
    'BackupManager',
    
    # Monitoring
    'StructuredLogger',
    'MetricsCollector',
    'monitor_operation',
    'HealthChecker',
    'AlertManager',
    'metrics_collector',
    'health_checker',
    'alert_manager',
    
    # Exceptions
    'JOJIAIException',
    'ValidationError',
    'InvalidSegment',
    'ConcurrencyError',
    'FileOperationError',
    'MemoryError',
    'WALError',
    'BackupError',
    'RecoveryError',
    
    # Utilities
    'get_version',
    'health_check',
    'VERSION_INFO'
]
