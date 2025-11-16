"""
Application-wide constants.

Centralize magic strings and configuration values here.

Why constants file?
- DRY: Define once, use everywhere
- Type safety: Enums provide validation
- Refactoring: Change in one place
- Documentation: Clear what values are valid
"""

from enum import Enum


# ========================================
# Decision Types
# ========================================

class DecisionType(str, Enum):
    """
    Possible decision outcomes from the Decision Service.
    
    Why str, Enum?
    - Inherits from str: Can be used as string ("ALLOW")
    - Inherits from Enum: IDE autocomplete, validation
    
    Usage:
        decision = DecisionType.ALLOW
        print(decision)  # "ALLOW"
        print(decision == "ALLOW")  # True
    """
    
    ALLOW = "ALLOW"
    """Action is permitted (no restrictions)."""
    
    DENY = "DENY"
    """Action is blocked (read-only mode active)."""
    
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    """Action requires human approval before proceeding."""
    
    POLICY_CHANGE = "POLICY_CHANGE"
    """Special receipt: Documents a policy rule change."""


# ========================================
# Rule Keys
# ========================================

class RuleKey(str, Enum):
    """
    Valid rule keys in the system.
    
    Only these two rules exist (from PDF spec).
    """
    
    WRITES_REQUIRE_APPROVAL = "writes_require_approval"
    """When enabled, all write actions require human approval."""
    
    READ_ONLY_FOR_RISKY = "read_only_for_risky"
    """When enabled, risky units are in read-only mode (writes denied)."""


# ========================================
# Action Prefixes
# ========================================

ACTION_PREFIX_READ = "read:"
ACTION_PREFIX_WRITE = "write:"

# ========================================
# Hash Algorithms
# ========================================

DEFAULT_HASH_ALGORITHM = "sha256"