
"""
Frank Mode++ Response Formatter
Structures responses in "Reasoning → Conclusion" format.
"""

import re
from typing import Dict, Optional


class FrankFormatter:
    """Formats responses in Frank Mode++ structure"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.anti_moralizing = config.get("anti_moralizing", True)
        self.max_disclaimer_lines = config.get("max_disclaimer_lines", 1)
    
    def format_response(self, reasoning: str, conclusion: str, 
                       disclaimer: Optional[str] = None) -> str:
        """
        Format response in Frank Mode++ structure
        
        Args:
            reasoning: Analysis and thought process
            conclusion: Direct answer or recommendation  
            disclaimer: Optional disclaimer (max 1 line)
            
        Returns:
            Formatted response string
        """
        # Clean up moralizing language if enabled
        if self.anti_moralizing:
            reasoning = self._remove_moralizing(reasoning)
            conclusion = self._remove_moralizing(conclusion)
        
        # Build response
        response_parts = []
        
        # Add disclaimer if provided (max 1 line)
        if disclaimer:
            clean_disclaimer = self._truncate_disclaimer(disclaimer)
            response_parts.append(clean_disclaimer)
            response_parts.append("")  # Empty line
        
        # Add structured content
        response_parts.extend([
            f"**Reasoning:** {reasoning.strip()}",
            "",
            f"**Conclusion:** {conclusion.strip()}"
        ])
        
        return "\n".join(response_parts)
    
    def format_refusal(self, refusal: str, alternatives: str, 
                      reasoning: Optional[str] = None) -> str:
        """Format refusal with alternatives in Frank structure"""
        if reasoning:
            reasoning_text = reasoning
        else:
            reasoning_text = "This request falls outside acceptable boundaries."
        
        conclusion_text = f"{refusal} {alternatives}"
        
        return self.format_response(reasoning_text, conclusion_text)
    
    def _remove_moralizing(self, text: str) -> str:
        """Remove excessive moralizing language"""
        # Patterns to remove or replace
        moralizing_patterns = [
            (r'\bI must emphasize that\b', ''),
            (r'\bIt\'s important to note that\b', ''),
            (r'\bI want to be clear that\b', ''),
            (r'\bPlease understand that\b', ''),
            (r'\bI feel obligated to mention\b', ''),
            (r'\bI should point out that\b', ''),
            (r'\bLet me be absolutely clear\b', ''),
            (r'\bI cannot stress enough\b', ''),
            (r'\bthis is important to note\b', ''),
            (r'\bimportant to note\b', ''),
        ]
        
        result = text
        for pattern, replacement in moralizing_patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    def _truncate_disclaimer(self, disclaimer: str) -> str:
        """Ensure disclaimer is maximum 1 line"""
        lines = disclaimer.strip().split('\n')
        if len(lines) <= self.max_disclaimer_lines:
            return disclaimer.strip()
        
        # Take first line and add ellipsis if truncated
        first_line = lines[0].strip()
        if len(lines) > 1:
            first_line += "..."
        
        return first_line
    
    def calculate_directness_score(self, text: str) -> int:
        """Calculate directness score (0-100)"""
        # Factors that reduce directness
        hedging_words = ['maybe', 'perhaps', 'possibly', 'might', 'could be']
        disclaimer_phrases = ['however', 'but', 'although', 'nevertheless']
        
        word_count = len(text.split())
        if word_count == 0:
            return 0
        
        # Count hedging and disclaimers
        hedging_count = sum(1 for word in hedging_words if word in text.lower())
        disclaimer_count = sum(1 for phrase in disclaimer_phrases if phrase in text.lower())
        
        # Calculate score (higher is more direct)
        penalty = (hedging_count + disclaimer_count) * 20  # Increased penalty
        base_score = 100 - min(penalty, 80)  # Cap penalty at 80 points
        
        return max(base_score, 20)  # Minimum score of 20
