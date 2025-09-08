
"""
Policy Router for Frank Mode++
Routes topics to appropriate handling based on content analysis.
"""

import re
from typing import Dict, List, Tuple, Optional
from enum import Enum


class PolicyLevel(Enum):
    """Policy enforcement levels"""
    ALLOW = "allow"
    FRANK_RESPONSE = "frank_response"  
    SOFT_REFUSAL = "soft_refusal"
    HARD_REFUSAL = "hard_refusal"


class PolicyRouter:
    """Routes requests to appropriate policy handling"""
    
    def __init__(self, config: Dict):
        self.config = config
        self._load_patterns()
    
    def _load_patterns(self):
        """Load keyword patterns for topic classification"""
        self.illegal_patterns = [
            r'\b(hack|crack|pirate|steal|fraud|scam)\b',
            r'\b(bomb|weapon|explosive|poison)\b',
            r'\b(drug\s+synthesis|meth|cocaine|heroin)\b',
            r'\bmake\s+a?\s*bombs?\b',
            r'\bforge\s+documents?\b',
            r'\bmake\s+bombs?\s+and\s+explosives\b'
        ]
        
        self.self_harm_patterns = [
            r'\b(suicide|self\s*harm|cut\s+myself|kill\s+myself)\b',
            r'\b(overdose|hanging|jumping)\b'
        ]
        
        self.graphic_patterns = [
            r'\b(gore|torture|mutilation|dismember)\b',
            r'\b(graphic\s+violence|brutal\s+murder)\b'
        ]
        
        self.sensitive_patterns = [
            r'\b(controversial|political|religious)\b',
            r'\b(conspiracy|misinformation)\b'
        ]
    
    def route_request(self, user_input: str) -> Tuple[PolicyLevel, Optional[str]]:
        """
        Route user request to appropriate policy level
        
        Returns:
            Tuple of (PolicyLevel, reason)
        """
        user_lower = user_input.lower()
        
        # Check for hard refusal patterns
        if self._matches_patterns(user_lower, self.illegal_patterns):
            return PolicyLevel.HARD_REFUSAL, "illegal_content"
            
        if self._matches_patterns(user_lower, self.self_harm_patterns):
            return PolicyLevel.HARD_REFUSAL, "self_harm"
            
        if self._matches_patterns(user_lower, self.graphic_patterns):
            return PolicyLevel.HARD_REFUSAL, "graphic_violence"
        
        # Check for soft refusal (frank response with caveats)
        if self._matches_patterns(user_lower, self.sensitive_patterns):
            return PolicyLevel.FRANK_RESPONSE, "sensitive_topic"
        
        # Default to frank response
        return PolicyLevel.FRANK_RESPONSE, None
    
    def _matches_patterns(self, text: str, patterns: List[str]) -> bool:
        """Check if text matches any pattern in the list"""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def get_policy_config(self, level: PolicyLevel) -> Dict:
        """Get configuration for specific policy level"""
        return self.config.get("policy_levels", {}).get(level.value, {})
