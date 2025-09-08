
"""Tests for monitoring and metrics system."""

import time
import pytest
import threading
from unittest.mock import patch, MagicMock

from jojiai.monitoring import (
    StructuredLogger, MetricsCollector, monitor_operation,
    HealthChecker, AlertManager, metrics_collector, health_checker, alert_manager
)


class TestStructuredLogger:
    """Test suite for StructuredLogger."""
    
    def test_logger_initialization(self):
        """Test logger initialization."""
        logger = StructuredLogger('test_logger', level='DEBUG')
        assert logger.logger.name == 'test_logger'
        assert logger.logger.level == 10  # DEBUG level
    
    def test_logger_with_file(self, tmp_path):
        """Test logger with file output."""
        log_file = tmp_path / 'test.log'
        logger = StructuredLogger('test_logger', log_file=str(log_file))
        
        logger.info('Test message', key='value')
        
        # Verify log file was created and contains message
        assert log_file.exists()
        log_content = log_file.read_text()
        assert 'Test message' in log_content
        assert 'key' in log_content
        assert 'value' in log_content
    
    def test_structured_logging(self):
        """Test structured logging with extra data."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            logger = StructuredLogger('test_logger')
            logger.info('Test message', user_id=123, action='test')
            
            # Verify logger was called with extra data
            mock_logger.info.assert_called_once_with(
                'Test message', 
                extra={'user_id': 123, 'action': 'test'}
            )
    
    def test_different_log_levels(self):
        """Test different log levels."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            logger = StructuredLogger('test_logger')
            
            logger.debug('Debug message', debug_data='test')
            logger.info('Info message', info_data='test')
            logger.warning('Warning message', warning_data='test')
            logger.error('Error message', error_data='test')
            
            # Verify all log levels were called
            mock_logger.debug.assert_called_once()
            mock_logger.info.assert_called_once()
            mock_logger.warning.assert_called_once()
            mock_logger.error.assert_called_once()


class TestMetricsCollector:
    """Test suite for MetricsCollector."""
    
    @patch('jojiai.monitoring.start_http_server')
    def test_metrics_collector_initialization(self, mock_start_server):
        """Test metrics collector initialization."""
        collector = MetricsCollector(port=8001)
        assert collector.port == 8001
        mock_start_server.assert_called_once_with(8001)
    
    @patch('jojiai.monitoring.OPERATION_COUNTER')
    @patch('jojiai.monitoring.OPERATION_DURATION')
    def test_record_operation(self, mock_duration, mock_counter):
        """Test operation recording."""
        collector = MetricsCollector()
        
        collector.record_operation('test_op', 1.5, 'success')
        
        # Verify metrics were recorded
        mock_counter.labels.assert_called_with(operation_type='test_op', status='success')
        mock_counter.labels().inc.assert_called_once()
        mock_duration.labels.assert_called_with(operation_type='test_op')
        mock_duration.labels().observe.assert_called_with(1.5)
    
    @patch('jojiai.monitoring.ERROR_COUNTER')
    def test_record_error(self, mock_error_counter):
        """Test error recording."""
        collector = MetricsCollector()
        
        collector.record_error('ValueError', 'memory_agent')
        
        mock_error_counter.labels.assert_called_with(
            error_type='ValueError', 
            component='memory_agent'
        )
        mock_error_counter.labels().inc.assert_called_once()
    
    @patch('jojiai.monitoring.RETRY_COUNTER')
    def test_record_retry(self, mock_retry_counter):
        """Test retry recording."""
        collector = MetricsCollector()
        
        collector.record_retry('file_operation')
        
        mock_retry_counter.labels.assert_called_with(operation_type='file_operation')
        mock_retry_counter.labels().inc.assert_called_once()
    
    @patch('jojiai.monitoring.MEMORY_USAGE')
    def test_set_memory_usage(self, mock_memory_usage):
        """Test memory usage recording."""
        collector = MetricsCollector()
        
        collector.set_memory_usage('heap', 1024000)
        
        mock_memory_usage.labels.assert_called_with(memory_type='heap')
        mock_memory_usage.labels().set.assert_called_with(1024000)
    
    @patch('jojiai.monitoring.CONCURRENT_OPERATIONS')
    def test_concurrent_operations_tracking(self, mock_concurrent):
        """Test concurrent operations tracking."""
        collector = MetricsCollector()
        
        collector.increment_concurrent_operations('test_op')
        collector.decrement_concurrent_operations('test_op')
        
        # Verify increment and decrement were called
        assert mock_concurrent.labels.call_count == 2
        mock_concurrent.labels().inc.assert_called_once()
        mock_concurrent.labels().dec.assert_called_once()


class TestMonitorOperationDecorator:
    """Test suite for monitor_operation decorator."""
    
    @patch('jojiai.monitoring.metrics_collector')
    def test_successful_operation_monitoring(self, mock_collector):
        """Test monitoring of successful operation."""
        @monitor_operation('test_operation')
        def test_function():
            time.sleep(0.1)
            return 'success'
        
        result = test_function()
        
        assert result == 'success'
        mock_collector.increment_concurrent_operations.assert_called_with('test_operation')
        mock_collector.decrement_concurrent_operations.assert_called_with('test_operation')
        mock_collector.record_operation.assert_called_once()
        
        # Verify operation was recorded as success
        call_args = mock_collector.record_operation.call_args
        assert call_args[0][0] == 'test_operation'  # operation_type
        assert call_args[0][2] == 'success'  # status
        assert call_args[0][1] > 0.1  # duration should be > 0.1 seconds
    
    @patch('jojiai.monitoring.metrics_collector')
    def test_failed_operation_monitoring(self, mock_collector):
        """Test monitoring of failed operation."""
        @monitor_operation('test_operation')
        def test_function():
            raise ValueError('Test error')
        
        with pytest.raises(ValueError):
            test_function()
        
        mock_collector.increment_concurrent_operations.assert_called_with('test_operation')
        mock_collector.decrement_concurrent_operations.assert_called_with('test_operation')
        mock_collector.record_operation.assert_called_once()
        mock_collector.record_error.assert_called_once()
        
        # Verify operation was recorded as error
        operation_call = mock_collector.record_operation.call_args
        assert operation_call[0][2] == 'error'  # status
        
        # Verify error was recorded
        error_call = mock_collector.record_error.call_args
        assert error_call[0][0] == 'ValueError'  # error_type


class TestHealthChecker:
    """Test suite for HealthChecker."""
    
    def test_health_checker_initialization(self):
        """Test health checker initialization."""
        checker = HealthChecker()
        assert checker.checks == {}
    
    def test_register_health_check(self):
        """Test registering health checks."""
        checker = HealthChecker()
        
        def dummy_check():
            return True
        
        checker.register_check('test_check', dummy_check, interval=30.0)
        
        assert 'test_check' in checker.checks
        assert checker.checks['test_check']['func'] == dummy_check
        assert checker.checks['test_check']['interval'] == 30.0
        assert checker.checks['test_check']['status'] == 'unknown'
    
    def test_get_health_status_all_healthy(self):
        """Test health status when all checks are healthy."""
        checker = HealthChecker()
        
        # Register healthy checks
        checker.register_check('check1', lambda: True)
        checker.register_check('check2', lambda: True)
        
        # Manually set status to healthy (simulating background checks)
        checker.checks['check1']['status'] = 'healthy'
        checker.checks['check2']['status'] = 'healthy'
        
        status = checker.get_health_status()
        
        assert status['overall_status'] == 'healthy'
        assert status['checks']['check1']['status'] == 'healthy'
        assert status['checks']['check2']['status'] == 'healthy'
    
    def test_get_health_status_with_unhealthy(self):
        """Test health status when some checks are unhealthy."""
        checker = HealthChecker()
        
        checker.register_check('healthy_check', lambda: True)
        checker.register_check('unhealthy_check', lambda: False)
        
        # Manually set status
        checker.checks['healthy_check']['status'] = 'healthy'
        checker.checks['unhealthy_check']['status'] = 'unhealthy'
        
        status = checker.get_health_status()
        
        assert status['overall_status'] == 'unhealthy'
        assert status['checks']['healthy_check']['status'] == 'healthy'
        assert status['checks']['unhealthy_check']['status'] == 'unhealthy'
    
    def test_get_health_status_with_errors(self):
        """Test health status when checks have errors."""
        checker = HealthChecker()
        
        checker.register_check('error_check', lambda: True)
        checker.checks['error_check']['status'] = 'error'
        
        status = checker.get_health_status()
        
        assert status['overall_status'] == 'unhealthy'
        assert status['checks']['error_check']['status'] == 'error'


class TestAlertManager:
    """Test suite for AlertManager."""
    
    def test_alert_manager_initialization(self):
        """Test alert manager initialization."""
        manager = AlertManager()
        assert manager.alert_rules == []
        assert manager.active_alerts == {}
    
    def test_add_alert_rule(self):
        """Test adding alert rules."""
        manager = AlertManager()
        
        def test_condition():
            return True
        
        manager.add_rule('test_alert', test_condition, severity='critical')
        
        assert len(manager.alert_rules) == 1
        assert manager.alert_rules[0]['name'] == 'test_alert'
        assert manager.alert_rules[0]['condition'] == test_condition
        assert manager.alert_rules[0]['severity'] == 'critical'
    
    def test_check_alerts_firing(self):
        """Test alert firing."""
        manager = AlertManager()
        
        # Add rule that should fire
        manager.add_rule('test_alert', lambda: True, severity='warning')
        
        with patch.object(manager, '_send_alert') as mock_send:
            manager.check_alerts()
            
            # Alert should be fired
            assert 'test_alert' in manager.active_alerts
            assert manager.active_alerts['test_alert']['status'] == 'firing'
            mock_send.assert_called_once()
    
    def test_check_alerts_resolving(self):
        """Test alert resolving."""
        manager = AlertManager()
        
        # Add rule and manually set as active
        manager.add_rule('test_alert', lambda: False, severity='warning')
        manager.active_alerts['test_alert'] = {
            'name': 'test_alert',
            'severity': 'warning',
            'timestamp': time.time(),
            'status': 'firing'
        }
        
        with patch.object(manager, '_send_alert') as mock_send:
            manager.check_alerts()
            
            # Alert should be resolved
            assert 'test_alert' not in manager.active_alerts
            mock_send.assert_called_once()
            
            # Verify resolved alert was sent
            call_args = mock_send.call_args[0][0]
            assert call_args['status'] == 'resolved'
    
    def test_get_active_alerts(self):
        """Test getting active alerts."""
        manager = AlertManager()
        
        # Manually add active alerts
        alert1 = {
            'name': 'alert1',
            'severity': 'warning',
            'timestamp': time.time(),
            'status': 'firing'
        }
        alert2 = {
            'name': 'alert2',
            'severity': 'critical',
            'timestamp': time.time(),
            'status': 'firing'
        }
        
        manager.active_alerts['alert1'] = alert1
        manager.active_alerts['alert2'] = alert2
        
        active_alerts = manager.get_active_alerts()
        
        assert len(active_alerts) == 2
        assert alert1 in active_alerts
        assert alert2 in active_alerts
    
    def test_alert_rule_error_handling(self):
        """Test error handling in alert rules."""
        manager = AlertManager()
        
        def failing_condition():
            raise Exception("Test error")
        
        manager.add_rule('failing_alert', failing_condition)
        
        # Should not raise exception
        manager.check_alerts()
        
        # Alert should not be active due to error
        assert 'failing_alert' not in manager.active_alerts


class TestGlobalInstances:
    """Test global monitoring instances."""
    
    def test_global_metrics_collector_exists(self):
        """Test that global metrics collector exists."""
        assert metrics_collector is not None
        assert isinstance(metrics_collector, MetricsCollector)
    
    def test_global_health_checker_exists(self):
        """Test that global health checker exists."""
        assert health_checker is not None
        assert isinstance(health_checker, HealthChecker)
    
    def test_global_alert_manager_exists(self):
        """Test that global alert manager exists."""
        assert alert_manager is not None
        assert isinstance(alert_manager, AlertManager)
