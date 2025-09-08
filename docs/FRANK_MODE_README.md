
# Frank Mode++ for JOJIAI/DeepAgent

A production-ready system for maximum directness and honesty in AI communication while maintaining essential safety guardrails.

## Overview

Frank Mode++ enables AI agents to communicate with unprecedented directness and candor, eliminating unnecessary hedging, disclaimers, and sycophantic behavior while preserving critical safety boundaries.

### Key Features

- **Maximum Directness**: Eliminates unnecessary hedging and qualifiers
- **Minimal Disclaimers**: Maximum 1 line disclaimers when absolutely necessary
- **Constructive Refusals**: Always provides alternatives when declining requests
- **Anti-Moralizing**: Removes excessive moral lecturing and value judgments
- **Structured Responses**: "Reasoning → Conclusion" format for clarity
- **Smart Routing**: Context-aware policy enforcement
- **Production Monitoring**: Comprehensive metrics and alerting
- **Safe Rollout**: Feature flags and canary deployment support

## Architecture

```
User Input
    ↓
Feature Flags Check
    ↓
Policy Router (Topic Classification)
    ↓
Lexical Filter (Content Filtering)
    ↓
Guardrails Check (Safety Validation)
    ↓
Response Generation
    ↓
Frank Formatter (Structure & Anti-Moralizing)
    ↓
Metrics Collection
    ↓
Final Response
```

## Quick Start

### 1. Installation

```bash
pip install prometheus_client pytest
```

### 2. Basic Usage

```python
from jojiai.frank_mode import (
    PolicyRouter, FrankFormatter, LexicalFilter, 
    FeatureFlags, FrankMetrics
)

# Initialize components
config = {
    "frank_mode_enabled": True,
    "anti_moralizing": True,
    "max_disclaimer_lines": 1,
    "metrics_enabled": True
}

router = PolicyRouter(config)
formatter = FrankFormatter(config)
filter = LexicalFilter(config)
flags = FeatureFlags()
metrics = FrankMetrics(config)

# Process request
def process_frank_request(user_input, user_id="anonymous"):
    # Check if enabled for user
    if not flags.is_frank_mode_enabled(user_id):
        return "Frank Mode++ not available"
    
    # Route and filter
    policy_level, reason = router.route_request(user_input)
    filtered_input, warnings = filter.filter_content(user_input)
    
    # Check safety
    is_violation, violation_type = filter.check_guardrails(filtered_input)
    
    if is_violation:
        # Generate refusal with alternatives
        from jojiai.frank_mode import RefusalTemplates
        refusal = RefusalTemplates.get_refusal(violation_type)
        alternatives = RefusalTemplates.get_alternatives(violation_type)
        response = formatter.format_refusal(refusal, " ".join(alternatives))
    else:
        # Generate frank response
        reasoning = "This request can be addressed directly and honestly."
        conclusion = "Here's my straightforward response without unnecessary hedging."
        response = formatter.format_response(reasoning, conclusion)
    
    # Record metrics
    scores = filter.calculate_content_score(response)
    metrics.record_request(policy_level.value, "success", 0.1, scores)
    
    return response
```

### 3. Configuration

Edit `config/joji_frank_mode.json`:

```json
{
  "frank_mode": {
    "enabled": true,
    "rollout_stage": "full"
  },
  "content_filtering": {
    "anti_moralizing": true,
    "max_hedging_words": 3
  },
  "response_formatting": {
    "max_disclaimer_lines": 1,
    "directness_optimization": true
  }
}
```

## Feature Management

### Enable Frank Mode++

```bash
# Via environment variable
export FRANK_MODE_FRANK_MODE_ENABLED=true

# Via feature flags CLI
python -m jojiai.frank_mode.feature_flags enable
```

### Rollout Stages

```bash
# Canary rollout (5% of users)
python -m jojiai.frank_mode.feature_flags rollout canary

# Beta rollout (25% of users)  
python -m jojiai.frank_mode.feature_flags rollout beta

# Full rollout (100% of users)
python -m jojiai.frank_mode.feature_flags rollout full
```

### Emergency Disable

```bash
# Immediate disable across all users
python -m jojiai.frank_mode.feature_flags emergency

# Or via environment
export FRANK_MODE_EMERGENCY_DISABLE=true
```

## Response Examples

### Before Frank Mode++
```
I understand you're asking about quantum physics. However, I should mention that this is a complex topic that requires careful explanation. I want to be clear that while I'll do my best to help, quantum mechanics involves many nuanced concepts that might be difficult to grasp initially. Please keep in mind that this is a simplified explanation.

Quantum physics is the study of matter and energy at the smallest scales...
```

### After Frank Mode++
```
**Reasoning:** Quantum physics is a well-established scientific field that can be explained clearly without excessive caveats.

**Conclusion:** Quantum physics studies matter and energy at atomic and subatomic scales. Unlike classical physics, quantum systems exhibit superposition (existing in multiple states simultaneously) and entanglement (instant correlation between particles regardless of distance). Key principles include wave-particle duality and the uncertainty principle.
```

## Policy Levels

### ALLOW
- No disclaimers
- Maximum directness
- Full anti-moralizing

### FRANK_RESPONSE  
- Up to 1 line disclaimer if needed
- Direct communication
- Anti-moralizing enabled

### SOFT_REFUSAL
- Brief refusal with alternatives
- Constructive suggestions
- Educational context when possible

### HARD_REFUSAL
- Clear boundary enforcement
- Multiple alternative options
- Safety-first approach

## Guardrails (Non-Negotiable)

1. **Illegal Content**: No guidance on illegal activities
2. **Self-Harm**: No self-harm instructions or methods
3. **Graphic Violence**: No detailed violence descriptions
4. **Personal Data**: No personal information exposure
5. **System Manipulation**: No jailbreaking or prompt injection

## Monitoring & Metrics

### Prometheus Metrics

```bash
# Start metrics server
python -m jojiai.frank_mode.frank_metrics
```

Available metrics:
- `frank_mode_requests_total` - Total requests by policy level
- `frank_mode_response_seconds` - Response time distribution
- `frank_mode_candor_score` - Current candor score (0-100)
- `frank_mode_directness_score` - Current directness score (0-100)
- `frank_mode_safety_score` - Current safety score (0-100)
- `frank_mode_refusals_total` - Refusals by reason
- `frank_mode_content_filtered_total` - Content filtering events

### Quality Scores

- **Candor Score**: Overall frankness metric (weighted average)
- **Directness Score**: Measures hedging and qualification usage
- **Safety Score**: Guardrail compliance (0 = violation, 100 = safe)
- **Usefulness Score**: Response length and detail level

## Testing

### Run Tests

```bash
# Core functionality tests
pytest tests/test_frank_mode_core.py -v

# Integration tests
pytest tests/test_frank_mode_integration.py -v

# All tests
pytest tests/test_frank_mode_*.py -v
```

### Test Categories

1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Full pipeline testing
3. **Edge Cases**: Boundary condition testing
4. **Safety Tests**: Guardrail validation
5. **Performance Tests**: Response time and throughput

## Deployment

### Production Checklist

- [ ] Feature flags configured
- [ ] Metrics collection enabled
- [ ] Alerting rules configured
- [ ] Canary rollout plan ready
- [ ] Emergency disable tested
- [ ] Safety guardrails validated
- [ ] Performance benchmarks established

### Rollout Process

1. **Canary (5%)**: Deploy to small user subset
2. **Monitor**: Watch metrics for 24-48 hours
3. **Beta (25%)**: Expand to larger group
4. **Monitor**: Validate quality scores
5. **Full (100%)**: Complete rollout
6. **Monitor**: Ongoing quality assurance

### Rollback Triggers

- Candor score < 60 for >1 hour
- Safety score < 90 for >10 minutes  
- User satisfaction < 70% for >2 hours
- Error rate > 5% for >30 minutes

## Troubleshooting

### Common Issues

**Frank Mode++ not activating**
- Check `FRANK_MODE_FRANK_MODE_ENABLED` environment variable
- Verify rollout percentage settings
- Confirm user is in rollout group

**Responses still hedged/qualified**
- Check `anti_moralizing` configuration
- Verify `max_disclaimer_lines` setting
- Review formatter configuration

**Safety violations not caught**
- Validate guardrail patterns
- Check lexical filter configuration
- Review policy router rules

**Metrics not collecting**
- Confirm `metrics_enabled: true`
- Check Prometheus server status
- Verify network connectivity

### Debug Mode

```bash
# Enable debug logging
export FRANK_MODE_LOG_LEVEL=DEBUG

# Check feature flag status
python -m jojiai.frank_mode.feature_flags status

# Test specific input
python -c "
from jojiai.frank_mode import PolicyRouter
router = PolicyRouter({})
print(router.route_request('your test input'))
"
```

## API Reference

### PolicyRouter

```python
router = PolicyRouter(config)
policy_level, reason = router.route_request(user_input)
```

### FrankFormatter

```python
formatter = FrankFormatter(config)
response = formatter.format_response(reasoning, conclusion, disclaimer)
directness_score = formatter.calculate_directness_score(text)
```

### LexicalFilter

```python
filter = LexicalFilter(config)
filtered_text, warnings = filter.filter_content(text)
is_violation, violation_type = filter.check_guardrails(text)
scores = filter.calculate_content_score(text)
```

### FeatureFlags

```python
flags = FeatureFlags()
is_enabled = flags.is_frank_mode_enabled(user_id)
flags.set_rollout_stage(RolloutStage.BETA, percentage=25)
flags.emergency_disable()
```

### FrankMetrics

```python
metrics = FrankMetrics(config)
metrics.record_request(policy_level, status, response_time, scores)
metrics.start_metrics_server(port=8000)
current_metrics = metrics.get_current_metrics()
```

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/frank-enhancement`
3. Add tests for new functionality
4. Ensure all tests pass: `pytest tests/`
5. Update documentation
6. Submit pull request

## License

This implementation is part of the JOJIAI/DeepAgent project. See main project license for details.

## Support

For issues and questions:
- Create GitHub issue with `frank-mode++` label
- Include configuration and error logs
- Provide minimal reproduction case
- Tag with appropriate priority level

---

**Remember**: Frank Mode++ is about honest, direct communication while respecting fundamental safety boundaries. The goal is maximum candor with minimum risk.
