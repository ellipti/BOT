"""
Position Netting Policy Configuration
Defines netting modes and reduce rules for position management.
"""

from enum import Enum
from typing import Literal


class NettingMode(str, Enum):
    """Position netting mode configuration."""
    
    NETTING = "NETTING"  # Net positions - opposite orders reduce existing positions
    HEDGING = "HEDGING"  # Hedge positions - allow multiple positions in same symbol


class ReduceRule(str, Enum):
    """Rules for reducing existing positions when netting."""
    
    FIFO = "FIFO"  # First In, First Out - close oldest positions first
    LIFO = "LIFO"  # Last In, First Out - close newest positions first  
    PROPORTIONAL = "PROPORTIONAL"  # Proportional reduction across all positions


# Type aliases for settings
NettingModeType = Literal["NETTING", "HEDGING"]
ReduceRuleType = Literal["FIFO", "LIFO", "PROPORTIONAL"]
