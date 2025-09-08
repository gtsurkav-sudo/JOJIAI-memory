
"""
Frank Mode++ Implementation for JOJIAI/DeepAgent

A system for maximum directness and honesty in AI communication
while maintaining essential safety guardrails.
"""

from .policy_router import PolicyRouter
from .refusal_templates import RefusalTemplates
from .formatter import FrankFormatter
from .lexical_filter import LexicalFilter
from .frank_metrics import FrankMetrics
from .feature_flags import FeatureFlags

__version__ = "1.0.0"
__all__ = [
    "PolicyRouter",
    "RefusalTemplates", 
    "FrankFormatter",
    "LexicalFilter",
    "FrankMetrics",
    "FeatureFlags"
]
