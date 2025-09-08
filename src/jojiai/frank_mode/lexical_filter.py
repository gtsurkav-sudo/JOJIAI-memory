
"""
Lexical Filter for Frank Mode++
Content filtering while maintaining directness.
"""

import re
from typing import List, Dict, Tuple, Optional


class LexicalFilter:
    """Filters content while preserving Frank Mode++ directness"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.strict_mode = config.get("strict_filtering", False)
        self._load_filter_patterns()
    
    def _load_filter_patterns(self):
        """Load filtering patterns"""
        # Hard filters - always blocked
        self.hard_filters = [
            r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',  # Email addresses
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN pattern
            r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit card pattern
        ]
        
        # Soft filters - flagged but may be allowed in Frank mode
        self.soft_filters = [
            r'\b(damn|hell|crap)\b',  # Mild profanity
            r'\b(controversial|sensitive)\b',  # Topic flags
        ]
        
        # Anti-moralizing patterns to remove
        self.moralizing_patterns = [
            r'I must remind you that',
            r'It\'s crucial to understand',
            r'Please be aware that',
            r'I feel compelled to mention',
            r'Let me emphasize the importance',
        ]
    
    def filter_content(self, text: str) -> Tuple[str, List[str]]:
        """
        Filter content and return cleaned text with warnings
        
        Returns:
            Tuple of (filtered_text, warnings)
        """
        warnings = []
        filtered_text = text
        
        # Apply hard filters
        for pattern in self.hard_filters:
            if re.search(pattern, filtered_text):
                filtered_text = re.sub(pattern, '[REDACTED]', filtered_text)
                warnings.append("Personal information redacted")
        
        # Check soft filters (warn but don't remove in Frank mode)
        if not self.config.get("frank_mode_enabled", True):
            for pattern in self.soft_filters:
                if re.search(pattern, filtered_text, re.IGNORECASE):
                    warnings.append("Content flagged for review")
        
        # Remove moralizing language
        if self.config.get("anti_moralizing", True):
            filtered_text = self._remove_moralizing(filtered_text)
        
        return filtered_text, warnings
    
    def _remove_moralizing(self, text: str) -> str:
        """Remove excessive moralizing language"""
        result = text
        for pattern in self.moralizing_patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        return result
    
    def check_guardrails(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if content violates non-negotiable guardrails
        
        Returns:
            Tuple of (is_violation, violation_type)
        """
        # Illegal content patterns
        illegal_patterns = [
            r'\b(how to make bombs|create explosives)\b',
            r'\b(hack into|break into|steal from)\b',
            r'\b(forge documents|fake ID)\b'
        ]
        
        # Self-harm patterns  
        self_harm_patterns = [
            r'\b(how to kill myself|suicide methods)\b',
            r'\b(self harm techniques|cutting methods)\b'
        ]
        
        # Check violations
        text_lower = text.lower()
        
        for pattern in illegal_patterns:
            if re.search(pattern, text_lower):
                return True, "illegal_content"
        
        for pattern in self_harm_patterns:
            if re.search(pattern, text_lower):
                return True, "self_harm"
        
        return False, None
    
    def calculate_content_score(self, text: str) -> Dict[str, int]:
        """Calculate content quality scores"""
        word_count = len(text.split())
        
        # Directness score (fewer hedging words = higher score)
        hedging_words = ['maybe', 'perhaps', 'possibly', 'might', 'could']
        hedging_count = sum(1 for word in hedging_words if word in text.lower())
        directness_score = max(100 - (hedging_count * 10), 0)
        
        # Usefulness score (longer, more detailed = higher score)
        usefulness_score = min(word_count * 2, 100)
        
        # Safety score (no violations = 100)
        is_violation, _ = self.check_guardrails(text)
        safety_score = 0 if is_violation else 100
        
        return {
            "directness": directness_score,
            "usefulness": usefulness_score,
            "safety": safety_score,
            "overall": (directness_score + usefulness_score + safety_score) // 3
        }
