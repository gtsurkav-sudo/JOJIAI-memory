
"""
Feature Flags for Frank Mode++ Rollout/Rollback
Environment-based feature flag system.
"""

import os
import json
from typing import Dict, Optional, Any
from enum import Enum


class RolloutStage(Enum):
    """Rollout stages for Frank Mode++"""
    DISABLED = "disabled"
    CANARY = "canary"  # 5% of users
    BETA = "beta"      # 25% of users  
    FULL = "full"      # 100% of users


class FeatureFlags:
    """Feature flag management for Frank Mode++"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "/tmp/frank_mode_flags.json"
        self.flags = self._load_flags()
    
    def _load_flags(self) -> Dict[str, Any]:
        """Load feature flags from environment and config file"""
        # Default flags
        default_flags = {
            "frank_mode_enabled": False,
            "rollout_stage": RolloutStage.DISABLED.value,
            "rollout_percentage": 0,
            "anti_moralizing": True,
            "strict_filtering": False,
            "metrics_enabled": True,
            "max_disclaimer_lines": 1,
            "emergency_disable": False
        }
        
        # Override with environment variables
        env_flags = {}
        for key in default_flags.keys():
            env_key = f"FRANK_MODE_{key.upper()}"
            if env_key in os.environ:
                value = os.environ[env_key]
                # Convert string values to appropriate types
                if value.lower() in ('true', 'false'):
                    env_flags[key] = value.lower() == 'true'
                elif value.isdigit():
                    env_flags[key] = int(value)
                else:
                    env_flags[key] = value
        
        # Load from config file if exists
        file_flags = {}
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    file_flags = json.load(f)
        except Exception:
            pass  # Ignore file loading errors
        
        # Merge flags (env > file > defaults)
        flags = {**default_flags, **file_flags, **env_flags}
        
        # Emergency disable check
        if flags.get("emergency_disable", False):
            flags["frank_mode_enabled"] = False
            flags["rollout_stage"] = RolloutStage.DISABLED.value
        
        return flags
    
    def is_frank_mode_enabled(self, user_id: Optional[str] = None) -> bool:
        """Check if Frank Mode++ is enabled for user"""
        if not self.flags.get("frank_mode_enabled", False):
            return False
        
        if self.flags.get("emergency_disable", False):
            return False
        
        rollout_stage_str = self.flags.get("rollout_stage", "disabled")
        try:
            rollout_stage = RolloutStage(rollout_stage_str)
        except ValueError:
            return False
        
        if rollout_stage == RolloutStage.DISABLED:
            return False
        elif rollout_stage == RolloutStage.FULL:
            return True
        else:
            # Percentage-based rollout
            percentage = self.flags.get("rollout_percentage", 0)
            if user_id:
                # Deterministic rollout based on user ID hash
                user_hash = hash(user_id) % 100
                return user_hash < percentage
            else:
                # Random rollout for anonymous users
                import random
                return random.randint(0, 99) < percentage
    
    def get_flag(self, flag_name: str, default: Any = None) -> Any:
        """Get specific feature flag value"""
        return self.flags.get(flag_name, default)
    
    def set_flag(self, flag_name: str, value: Any, persist: bool = True):
        """Set feature flag value"""
        self.flags[flag_name] = value
        
        if persist:
            self._save_flags()
    
    def _save_flags(self):
        """Save flags to config file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.flags, f, indent=2)
        except Exception:
            pass  # Ignore save errors
    
    def emergency_disable(self):
        """Emergency disable Frank Mode++"""
        self.set_flag("emergency_disable", True)
        self.set_flag("frank_mode_enabled", False)
        self.set_flag("rollout_stage", RolloutStage.DISABLED.value)
    
    def set_rollout_stage(self, stage: RolloutStage, percentage: Optional[int] = None):
        """Set rollout stage and percentage"""
        self.set_flag("rollout_stage", stage.value)
        
        if percentage is not None:
            self.set_flag("rollout_percentage", percentage)
        elif stage == RolloutStage.CANARY:
            self.set_flag("rollout_percentage", 5)
        elif stage == RolloutStage.BETA:
            self.set_flag("rollout_percentage", 25)
        elif stage == RolloutStage.FULL:
            self.set_flag("rollout_percentage", 100)
    
    def get_config(self) -> Dict[str, Any]:
        """Get all configuration flags"""
        return self.flags.copy()
    
    def reload_flags(self):
        """Reload flags from environment and config file"""
        self.flags = self._load_flags()


# CLI utility for flag management
if __name__ == "__main__":
    import sys
    
    flags = FeatureFlags()
    
    if len(sys.argv) < 2:
        print("Usage: python feature_flags.py <command> [args]")
        print("Commands:")
        print("  status - Show current flag status")
        print("  enable - Enable Frank Mode++")
        print("  disable - Disable Frank Mode++")
        print("  emergency - Emergency disable")
        print("  rollout <stage> [percentage] - Set rollout stage")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "status":
        print("Frank Mode++ Feature Flags:")
        for key, value in flags.get_config().items():
            print(f"  {key}: {value}")
    
    elif command == "enable":
        flags.set_flag("frank_mode_enabled", True)
        flags.set_flag("emergency_disable", False)
        print("Frank Mode++ enabled")
    
    elif command == "disable":
        flags.set_flag("frank_mode_enabled", False)
        print("Frank Mode++ disabled")
    
    elif command == "emergency":
        flags.emergency_disable()
        print("Frank Mode++ emergency disabled")
    
    elif command == "rollout":
        if len(sys.argv) < 3:
            print("Usage: rollout <stage> [percentage]")
            sys.exit(1)
        
        stage_name = sys.argv[2]
        percentage = int(sys.argv[3]) if len(sys.argv) > 3 else None
        
        try:
            stage = RolloutStage(stage_name)
            flags.set_rollout_stage(stage, percentage)
            print(f"Rollout stage set to {stage_name}")
        except ValueError:
            print(f"Invalid stage: {stage_name}")
            print("Valid stages: disabled, canary, beta, full")
    
    else:
        print(f"Unknown command: {command}")
