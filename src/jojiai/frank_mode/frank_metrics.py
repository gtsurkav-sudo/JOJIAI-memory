
"""
Frank Mode++ Metrics and Monitoring
Prometheus metrics for system performance and quality.
"""

import time
import json
import logging
from typing import Dict, Optional
from prometheus_client import Counter, Histogram, Gauge, start_http_server, CollectorRegistry


class FrankMetrics:
    """Metrics collection for Frank Mode++"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.metrics_enabled = config.get("metrics_enabled", True)
        self.registry = CollectorRegistry()  # Create separate registry for each instance
        
        if self.metrics_enabled:
            self._init_metrics()
            self._setup_logging()
    
    def _init_metrics(self):
        """Initialize Prometheus metrics"""
        # Request counters
        self.request_total = Counter(
            'frank_mode_requests_total',
            'Total Frank Mode++ requests',
            ['policy_level', 'status'],
            registry=self.registry
        )
        
        # Response time histogram
        self.response_time = Histogram(
            'frank_mode_response_seconds',
            'Frank Mode++ response time',
            ['policy_level'],
            registry=self.registry
        )
        
        # Quality gauges
        self.candor_score = Gauge(
            'frank_mode_candor_score',
            'Current candor score (0-100)',
            registry=self.registry
        )
        
        self.directness_score = Gauge(
            'frank_mode_directness_score', 
            'Current directness score (0-100)',
            registry=self.registry
        )
        
        self.safety_score = Gauge(
            'frank_mode_safety_score',
            'Current safety score (0-100)',
            registry=self.registry
        )
        
        # Refusal tracking
        self.refusals_total = Counter(
            'frank_mode_refusals_total',
            'Total refusals by reason',
            ['reason'],
            registry=self.registry
        )
        
        # Filter metrics
        self.content_filtered = Counter(
            'frank_mode_content_filtered_total',
            'Content filtering events',
            ['filter_type'],
            registry=self.registry
        )
    
    def _setup_logging(self):
        """Setup structured JSON logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(message)s'
        )
        self.logger = logging.getLogger('frank_mode')
    
    def record_request(self, policy_level: str, status: str, 
                      response_time: float, scores: Dict[str, int]):
        """Record request metrics"""
        if not self.metrics_enabled:
            return
        
        # Update counters and histograms
        self.request_total.labels(policy_level=policy_level, status=status).inc()
        self.response_time.labels(policy_level=policy_level).observe(response_time)
        
        # Update quality scores
        self.directness_score.set(scores.get('directness', 0))
        self.safety_score.set(scores.get('safety', 0))
        
        # Calculate and update candor score
        candor = self._calculate_candor_score(scores)
        self.candor_score.set(candor)
        
        # Log structured data
        self._log_request(policy_level, status, response_time, scores, candor)
    
    def record_refusal(self, reason: str):
        """Record refusal event"""
        if not self.metrics_enabled:
            return
        
        self.refusals_total.labels(reason=reason).inc()
        
        self.logger.info(json.dumps({
            'event': 'refusal',
            'reason': reason,
            'timestamp': time.time()
        }))
    
    def record_content_filter(self, filter_type: str):
        """Record content filtering event"""
        if not self.metrics_enabled:
            return
        
        self.content_filtered.labels(filter_type=filter_type).inc()
    
    def _calculate_candor_score(self, scores: Dict[str, int]) -> int:
        """
        Calculate overall candor score heuristic
        Combines directness, usefulness, and safety
        """
        directness = scores.get('directness', 0)
        usefulness = scores.get('usefulness', 0) 
        safety = scores.get('safety', 0)
        
        # Weighted average: directness 40%, usefulness 40%, safety 20%
        candor = int(directness * 0.4 + usefulness * 0.4 + safety * 0.2)
        return min(max(candor, 0), 100)
    
    def _log_request(self, policy_level: str, status: str, 
                    response_time: float, scores: Dict[str, int], candor: int):
        """Log structured request data"""
        log_data = {
            'event': 'frank_mode_request',
            'policy_level': policy_level,
            'status': status,
            'response_time': response_time,
            'scores': scores,
            'candor_score': candor,
            'timestamp': time.time()
        }
        
        self.logger.info(json.dumps(log_data))
    
    def start_metrics_server(self, port: int = 8000):
        """Start Prometheus metrics HTTP server"""
        if self.metrics_enabled:
            start_http_server(port)
            self.logger.info(f"Frank Mode++ metrics server started on port {port}")
    
    def get_current_metrics(self) -> Dict:
        """Get current metric values for monitoring"""
        if not self.metrics_enabled:
            return {}
        
        try:
            return {
                'candor_score': self.candor_score._value._value if hasattr(self.candor_score, '_value') else 0,
                'directness_score': self.directness_score._value._value if hasattr(self.directness_score, '_value') else 0,
                'safety_score': self.safety_score._value._value if hasattr(self.safety_score, '_value') else 0,
                'total_requests': sum(
                    sample.value for sample in self.request_total.collect()[0].samples
                ) if hasattr(self.request_total, 'collect') else 0
            }
        except Exception:
            # Return default values if metrics access fails
            return {
                'candor_score': 0,
                'directness_score': 0,
                'safety_score': 0,
                'total_requests': 0
            }


# Standalone metrics server for testing
if __name__ == "__main__":
    config = {"metrics_enabled": True}
    metrics = FrankMetrics(config)
    metrics.start_metrics_server(8000)
    
    print("Frank Mode++ metrics server running on http://localhost:8000/metrics")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down metrics server")
