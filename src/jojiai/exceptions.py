
"""Custom exceptions for JOJI Oi system."""

class JOJIAIException(Exception):
    """Base exception for JOJI Oi system."""
    pass


class ValidationError(JOJIAIException):
    """Raised when data validation fails."""
    pass


class InvalidSegment(ValidationError):
    """Raised when memory segment is invalid."""
    pass


class ConcurrencyError(JOJIAIException):
    """Raised when concurrent access issues occur."""
    pass


class FileOperationError(JOJIAIException):
    """Raised when file operations fail."""
    pass


class MemoryError(JOJIAIException):
    """Raised when memory operations fail."""
    pass


class WALError(JOJIAIException):
    """Raised when Write-Ahead Log operations fail."""
    pass


class BackupError(JOJIAIException):
    """Raised when backup operations fail."""
    pass


class RecoveryError(JOJIAIException):
    """Raised when recovery operations fail."""
    pass
