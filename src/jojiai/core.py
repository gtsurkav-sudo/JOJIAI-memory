
"""Enhanced core JOJIAI functionality with monitoring integration."""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from .exceptions import JOJIAIException, ValidationError
from .validation import validate_config, sanitize_input
from .monitoring import StructuredLogger, monitor_operation, metrics_collector
from .memory_agent import MemoryAgent
from .chat_memory import ChatMemory


class JOJIAICore:
    """Enhanced core JOJIAI processing engine with monitoring and memory integration."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, memory_path: Optional[str] = None):
        """Initialize JOJIAI core with optional configuration.
        
        Args:
            config: Optional configuration dictionary
            memory_path: Optional path to memory storage
        """
        self.config = config or {}
        self.memory_path = memory_path or self.config.get('memory_path', './memory')
        self.initialized = False
        self.version = "1.0.0"
        
        # Initialize structured logging
        log_level = self.config.get('log_level', 'INFO')
        log_file = self.config.get('log_file')
        self.logger = StructuredLogger('jojiai.core', level=log_level, log_file=log_file)
        
        # Initialize memory components
        self.memory_agent = None
        self.chat_memory = None
        
        # Setup system
        self._setup_system()
        
        self.logger.info("JOJIAI Core initialized", 
                        version=self.version,
                        memory_path=self.memory_path,
                        config_keys=len(self.config.keys()))
        
    def _setup_system(self):
        """Setup core system components."""
        try:
            # Validate configuration if provided
            if self.config:
                # Only validate if we have required keys
                required_keys = ['memory_path', 'backup_path', 'wal_path']
                if all(key in self.config for key in required_keys):
                    validate_config(self.config)
            
            # Initialize memory components
            self.memory_agent = MemoryAgent(self.memory_path, self.config)
            self.chat_memory = ChatMemory(self.memory_path, self.config)
            
            # Record system startup metrics
            metrics_collector.record_operation('system_startup', 0.0, 'success')
            
            self.initialized = True
            
        except Exception as e:
            self.logger.error("Failed to setup system", error=str(e), error_type=type(e).__name__)
            metrics_collector.record_error(type(e).__name__, 'core_setup')
            raise JOJIAIException(f"System setup failed: {e}")
    
    @monitor_operation('process_data')
    def process_data(self, data: Union[List[Any], str, int, float]) -> List[Any]:
        """Process input data and return transformed results.
        
        Args:
            data: Input data to process
            
        Returns:
            List of processed data items
            
        Raises:
            ValidationError: If data is invalid
        """
        if data is None:
            raise ValidationError("Data cannot be None")
        
        # Sanitize input data
        sanitized_data = sanitize_input(data)
        
        if isinstance(sanitized_data, (list, tuple)):
            if not sanitized_data:
                raise ValidationError("Data cannot be empty")
            result = [self._transform_item(item) for item in sanitized_data]
        else:
            result = [self._transform_item(sanitized_data)]
        
        self.logger.debug("Data processed successfully", 
                         input_type=type(data).__name__,
                         output_count=len(result))
        
        return result
    
    def _transform_item(self, item: Any) -> Any:
        """Transform a single data item.
        
        Args:
            item: Item to transform
            
        Returns:
            Transformed item
        """
        if isinstance(item, str):
            return item.upper()
        elif isinstance(item, (int, float)):
            return item * 2
        else:
            return str(item).upper()
    
    @monitor_operation('validate_input')
    def validate_input(self, data: Any) -> bool:
        """Validate input data.
        
        Args:
            data: Data to validate
            
        Returns:
            True if data is valid, False otherwise
        """
        if data is None:
            return False
        if isinstance(data, (list, tuple)) and len(data) == 0:
            return False
        if isinstance(data, str) and len(data.strip()) == 0:
            return False
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status.
        
        Returns:
            Dictionary containing system status information
        """
        status = {
            "initialized": self.initialized,
            "version": self.version,
            "config_keys": len(self.config.keys()),
            "has_config": bool(self.config),
            "memory_path": str(self.memory_path),
            "components": {
                "memory_agent": self.memory_agent is not None,
                "chat_memory": self.chat_memory is not None
            }
        }
        
        # Add memory statistics if available
        if self.memory_agent:
            try:
                memory_stats = self.memory_agent.get_memory_stats()
                status["memory_stats"] = memory_stats
            except Exception as e:
                self.logger.warning("Failed to get memory stats", error=str(e))
                status["memory_stats"] = {"error": str(e)}
        
        # Add chat statistics if available
        if self.chat_memory:
            try:
                chat_stats = self.chat_memory.get_chat_stats()
                status["chat_stats"] = chat_stats
            except Exception as e:
                self.logger.warning("Failed to get chat stats", error=str(e))
                status["chat_stats"] = {"error": str(e)}
        
        return status
    
    @monitor_operation('update_config')
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update system configuration.
        
        Args:
            new_config: New configuration to merge
            
        Raises:
            ValidationError: If configuration is invalid
        """
        if not isinstance(new_config, dict):
            raise ValidationError("Configuration must be a dictionary")
        
        # Sanitize configuration
        sanitized_config = sanitize_input(new_config)
        
        # Validate new configuration
        merged_config = self.config.copy()
        merged_config.update(sanitized_config)
        
        # Only validate if we have required keys
        required_keys = ['memory_path', 'backup_path', 'wal_path']
        if all(key in merged_config for key in required_keys):
            validate_config(merged_config)
        
        # Update configuration
        self.config.update(sanitized_config)
        
        # Reinitialize logging if log level changed
        if 'log_level' in sanitized_config:
            log_level = sanitized_config['log_level']
            log_file = self.config.get('log_file')
            self.logger = StructuredLogger('jojiai.core', level=log_level, log_file=log_file)
        
        self.logger.info("Configuration updated", 
                        updated_keys=list(sanitized_config.keys()),
                        total_keys=len(self.config.keys()))
    
    @monitor_operation('add_message')
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add message to chat memory.
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Message ID
            
        Raises:
            JOJIAIException: If chat memory is not initialized
        """
        if not self.chat_memory:
            raise JOJIAIException("Chat memory not initialized")
        
        message_id = self.chat_memory.add_message(role, content, metadata)
        
        self.logger.info("Message added to chat", 
                        message_id=message_id,
                        role=role,
                        content_length=len(content))
        
        return message_id
    
    @monitor_operation('get_conversation_history')
    def get_conversation_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get conversation history.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of messages
            
        Raises:
            JOJIAIException: If chat memory is not initialized
        """
        if not self.chat_memory:
            raise JOJIAIException("Chat memory not initialized")
        
        history = self.chat_memory.get_conversation_history(limit=limit)
        
        self.logger.debug("Retrieved conversation history", 
                         message_count=len(history),
                         limit=limit)
        
        return history
    
    @monitor_operation('store_decision')
    def store_decision(self, decision: Dict[str, Any]) -> str:
        """Store decision in memory.
        
        Args:
            decision: Decision data to store
            
        Returns:
            Decision ID
            
        Raises:
            JOJIAIException: If memory agent is not initialized
        """
        if not self.memory_agent:
            raise JOJIAIException("Memory agent not initialized")
        
        decision_id = self.memory_agent.store_decision(decision)
        
        self.logger.info("Decision stored", 
                        decision_id=decision_id,
                        decision_keys=list(decision.keys()))
        
        return decision_id
    
    @monitor_operation('create_backup')
    def create_backup(self, backup_name: Optional[str] = None) -> str:
        """Create system backup.
        
        Args:
            backup_name: Optional backup name
            
        Returns:
            Backup identifier
            
        Raises:
            JOJIAIException: If memory agent is not initialized
        """
        if not self.memory_agent:
            raise JOJIAIException("Memory agent not initialized")
        
        backup_id = self.memory_agent.create_snapshot(backup_name)
        
        self.logger.info("Backup created", 
                        backup_id=backup_id,
                        backup_name=backup_name)
        
        return backup_id
    
    def get_health(self) -> Dict[str, Any]:
        """Get system health status.
        
        Returns:
            Health status dictionary
        """
        health = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": self.version,
            "initialized": self.initialized,
            "components": {}
        }
        
        # Check memory agent health
        if self.memory_agent:
            try:
                stats = self.memory_agent.get_memory_stats()
                health["components"]["memory_agent"] = {
                    "status": "healthy",
                    "dialogues": stats.get("dialogues_count", 0),
                    "decisions": stats.get("decisions_count", 0)
                }
            except Exception as e:
                health["components"]["memory_agent"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health["status"] = "degraded"
        else:
            health["components"]["memory_agent"] = {
                "status": "not_initialized"
            }
            health["status"] = "degraded"
        
        # Check chat memory health
        if self.chat_memory:
            try:
                stats = self.chat_memory.get_chat_stats()
                health["components"]["chat_memory"] = {
                    "status": "healthy",
                    "messages": stats.get("total_messages", 0)
                }
            except Exception as e:
                health["components"]["chat_memory"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health["status"] = "degraded"
        else:
            health["components"]["chat_memory"] = {
                "status": "not_initialized"
            }
            health["status"] = "degraded"
        
        return health
    
    @monitor_operation('reset_system')
    def reset(self) -> None:
        """Reset the system to initial state."""
        self.logger.warning("System reset initiated")
        
        # Close existing components
        if self.memory_agent:
            self.memory_agent.close()
        if self.chat_memory:
            self.chat_memory.close()
        
        # Reset state
        self.config = {}
        self.initialized = False
        self.memory_agent = None
        self.chat_memory = None
        
        # Reinitialize
        self._setup_system()
        
        self.logger.info("System reset completed")
    
    def close(self) -> None:
        """Close system and cleanup resources."""
        self.logger.info("Shutting down JOJIAI Core")
        
        try:
            if self.memory_agent:
                self.memory_agent.close()
            if self.chat_memory:
                self.chat_memory.close()
                
            metrics_collector.record_operation('system_shutdown', 0.0, 'success')
            
        except Exception as e:
            self.logger.error("Error during shutdown", error=str(e))
            metrics_collector.record_error(type(e).__name__, 'core_shutdown')
        
        self.logger.info("JOJIAI Core shutdown completed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# HTTP server for health checks and metrics (optional)
def create_http_server(core: JOJIAICore, port: int = 8001):
    """Create HTTP server for health checks.
    
    Args:
        core: JOJIAI core instance
        port: Server port
        
    Returns:
        HTTP server instance
    """
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import json
        
        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/health':
                    health = core.get_health()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(health).encode())
                elif self.path == '/status':
                    status = core.get_status()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(status).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                # Suppress default logging
                pass
        
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        return server
        
    except ImportError:
        # HTTP server not available
        return None


if __name__ == '__main__':
    # Example usage
    config = {
        'memory_path': './memory',
        'backup_path': './backups',
        'wal_path': './memory/memory.wal',
        'log_level': 'INFO'
    }
    
    with JOJIAICore(config) as core:
        # Add some test data
        message_id = core.add_message('user', 'Hello, JOJI Oi!')
        decision_id = core.store_decision({
            'action': 'greet_user',
            'reasoning': 'User said hello',
            'confidence': 0.95
        })
        
        # Get status
        status = core.get_status()
        print(f"System status: {status}")
        
        # Create backup
        backup_id = core.create_backup('example_backup')
        print(f"Backup created: {backup_id}")
