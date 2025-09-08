
"""
Minimal refusal templates for Frank Mode++
Maximum 1 line refusals with constructive alternatives.
"""

from typing import Dict, List
from .policy_router import PolicyLevel


class RefusalTemplates:
    """Minimal refusal templates with alternatives"""
    
    TEMPLATES = {
        "illegal_content": {
            "refusal": "I can't provide guidance on illegal activities.",
            "alternatives": [
                "I can discuss legal alternatives or general information about the topic.",
                "I can explain relevant laws and regulations instead.",
                "I can suggest legitimate resources for your underlying need."
            ]
        },
        
        "self_harm": {
            "refusal": "I can't provide self-harm instructions.",
            "alternatives": [
                "I can connect you with mental health resources and crisis support.",
                "I can discuss healthy coping strategies and stress management.",
                "I can provide information about professional help options."
            ]
        },
        
        "graphic_violence": {
            "refusal": "I won't describe graphic violence in detail.",
            "alternatives": [
                "I can discuss the topic in general, educational terms.",
                "I can provide historical or sociological context instead.",
                "I can suggest academic resources on the subject."
            ]
        },
        
        "personal_data": {
            "refusal": "I can't access or generate personal information.",
            "alternatives": [
                "I can explain privacy best practices instead.",
                "I can discuss general information about the topic.",
                "I can suggest official channels for legitimate requests."
            ]
        },
        
        "system_manipulation": {
            "refusal": "I can't help with system manipulation or jailbreaking.",
            "alternatives": [
                "I can discuss AI safety and alignment topics openly.",
                "I can explain how AI systems work in general terms.",
                "I can address your underlying question directly."
            ]
        }
    }
    
    @classmethod
    def get_refusal(cls, reason: str) -> str:
        """Get minimal refusal message"""
        template = cls.TEMPLATES.get(reason, {})
        return template.get("refusal", "I can't assist with that request.")
    
    @classmethod
    def get_alternatives(cls, reason: str) -> List[str]:
        """Get constructive alternatives"""
        template = cls.TEMPLATES.get(reason, {})
        return template.get("alternatives", [
            "I can help you explore related topics that don't raise concerns.",
            "I can provide general information about the subject area.",
            "I can suggest alternative approaches to your underlying goal."
        ])
    
    @classmethod
    def format_refusal_with_alternatives(cls, reason: str) -> str:
        """Format complete refusal with alternatives"""
        refusal = cls.get_refusal(reason)
        alternatives = cls.get_alternatives(reason)
        
        alt_text = " ".join([f"• {alt}" for alt in alternatives])
        return f"{refusal} Instead: {alt_text}"
