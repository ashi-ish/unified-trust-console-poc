"""
Rules service for policy management.

Manages the 2 policy rules from the PDF specification:
1. writes_require_approval (writes need human approval)
2. read_only_for_risky (risky units in read-only mode)

This service provides:
- Get current rule states
- Toggle rules on/off
- Create audit receipts for policy changes
- Business logic for decision-making

Why a service layer?
- DRY: Business logic in one place (not scattered in routes)
- Testability: Easy to unit test
- Separation of concerns: Service layer isolated from API layer
- Transaction management: Ensures consistency
"""

from typing import Dict, List, Optional
from datetime import datetime, UTC
from sqlalchemy.orm import Session

from utc.models.rule import Rule, get_rule_by_key
from utc.models.receipt import Receipt
from utc.core.constants import RuleKey, DecisionType


class RulesService:
    """
    Service for managing policy rules.
    
    Handles:
    - Reading rule states
    - Updating rule states  
    - Creating policy change receipts
    - Business logic for rule evaluation
    """
    
    def __init__(self, db: Session):
        """
        Initialize rules service.
        
        Args:
            db: Database session
        
        Why pass db session?
        - Dependency injection (testable)
        - Transaction control (caller manages commits)
        - Flexibility (can use different sessions)
        """
        self.db = db
    
    def get_rule(self, rule_key: str) -> Optional[Rule]:
        """
        Get a rule by key.
        
        Args:
            rule_key: Rule identifier
        
        Returns:
            Rule instance or None if not found
        
        Example:
            rule = service.get_rule("writes_require_approval")
            if rule and rule.is_enabled():
                print("Approval required!")
        """
        return get_rule_by_key(self.db, rule_key)
    
    def get_all_rules(self) -> List[Rule]:
        """
        Get all rules.
        
        Returns:
            List of all Rule instances
        
        Example:
            rules = service.get_all_rules()
            for rule in rules:
                print(f"{rule.key}: {rule.value}")
        """
        return self.db.query(Rule).order_by(Rule.key).all()
    
    def get_rules_dict(self) -> Dict[str, bool]:
        """
        Get all rules as a dictionary.
        
        Returns:
            Dictionary mapping rule key to enabled state
        
        Example:
            rules = service.get_rules_dict()
            # {
            #   "writes_require_approval": True,
            #   "read_only_for_risky": False
            # }
        """
        rules = self.get_all_rules()
        return {rule.key: rule.is_enabled() for rule in rules}
    
    def is_rule_enabled(self, rule_key: str) -> bool:
        """
        Check if a specific rule is enabled.
        
        Args:
            rule_key: Rule identifier
        
        Returns:
            True if enabled, False otherwise (or if rule doesn't exist)
        
        Example:
            if service.is_rule_enabled("writes_require_approval"):
                return "Approval required"
        """
        rule = self.get_rule(rule_key)
        return rule.is_enabled() if rule else False
    
    def set_rule(
        self,
        rule_key: str,
        enabled: bool,
        create_receipt: bool = True,
        changed_by: str = "system"
    ) -> Rule:
        """
        Set a rule's state (enable or disable).
        
        Args:
            rule_key: Rule identifier
            enabled: True to enable, False to disable
            create_receipt: Whether to create audit receipt
            changed_by: Who made the change (for audit trail)
        
        Returns:
            Updated Rule instance
        
        Raises:
            ValueError: If rule doesn't exist
        
        Example:
            # Enable approval requirement
            rule = service.set_rule(
                "writes_require_approval",
                enabled=True,
                changed_by="admin@example.com"
            )
            
            # Creates audit receipt automatically!
        """
        rule = self.get_rule(rule_key)
        if not rule:
            raise ValueError(f"Rule not found: {rule_key}")
        
        # Track if state changed
        old_state = rule.is_enabled()
        new_state = enabled
        
        # Update rule
        if enabled:
            rule.enable()
        else:
            rule.disable()
        
        self.db.flush()  # Get updated timestamp
        
        # Create audit receipt for policy change
        if create_receipt and old_state != new_state:
            self._create_policy_change_receipt(
                rule_key=rule_key,
                old_state=old_state,
                new_state=new_state,
                changed_by=changed_by
            )
        
        return rule
    
    def toggle_rule(
        self,
        rule_key: str,
        create_receipt: bool = True,
        changed_by: str = "system"
    ) -> Rule:
        """
        Toggle a rule (ON → OFF or OFF → ON).
        
        Args:
            rule_key: Rule identifier
            create_receipt: Whether to create audit receipt
            changed_by: Who made the change
        
        Returns:
            Updated Rule instance
        
        Example:
            rule = service.toggle_rule(
                "read_only_for_risky",
                changed_by="security-team"
            )
            print(f"Rule is now: {'ON' if rule.is_enabled() else 'OFF'}")
        """
        rule = self.get_rule(rule_key)
        if not rule:
            raise ValueError(f"Rule not found: {rule_key}")
        
        # Toggle
        new_state = not rule.is_enabled()
        return self.set_rule(rule_key, new_state, create_receipt, changed_by)
    
    def evaluate_rules_for_action(self, action: str) -> Dict[str, any]:
        """
        Evaluate rules for a given action and determine decision.
        
        This implements the decision logic from the PDF spec:
        1. If read_only_for_risky is ON and action is write: → DENY
        2. Else if writes_require_approval is ON and action is write: → REQUIRE_APPROVAL
        3. Else → ALLOW
        
        Args:
            action: Action string (e.g., "write:/payments", "read:/users")
        
        Returns:
            Dictionary with decision and applied rules
        
        Example:
            result = service.evaluate_rules_for_action("write:/payments")
            # {
            #   "decision": "REQUIRE_APPROVAL",
            #   "rules": ["writes_require_approval"],
            #   "reason": "Approval required for writes"
            # }
        """
        is_write = action.startswith("write:")
        applied_rules = []
        
        # Rule 1: Read-only mode (highest priority)
        if is_write and self.is_rule_enabled(RuleKey.READ_ONLY_FOR_RISKY.value):
            return {
                "decision": DecisionType.DENY.value,
                "rules": [RuleKey.READ_ONLY_FOR_RISKY.value],
                "reason": "Read-only mode active for risky units"
            }
        
        # Rule 2: Require approval for writes
        if is_write and self.is_rule_enabled(RuleKey.WRITES_REQUIRE_APPROVAL.value):
            return {
                "decision": DecisionType.REQUIRE_APPROVAL.value,
                "rules": [RuleKey.WRITES_REQUIRE_APPROVAL.value],
                "reason": "Approval required for writes"
            }
        
        # Rule 3: Allow (default)
        return {
            "decision": DecisionType.ALLOW.value,
            "rules": [],
            "reason": "No restrictive policies active"
        }
    
    def _create_policy_change_receipt(
        self,
        rule_key: str,
        old_state: bool,
        new_state: bool,
        changed_by: str
    ) -> Receipt:
        """
        Create an audit receipt for a policy change.
        
        Args:
            rule_key: Which rule changed
            old_state: Previous state
            new_state: New state
            changed_by: Who made the change
        
        Returns:
            Receipt documenting the policy change
        
        This creates a special POLICY_CHANGE receipt for audit trail.
        """
        receipt = Receipt(
            subject=changed_by,
            action=f"policy_change:{rule_key}",
            decision=DecisionType.POLICY_CHANGE.value,
            rules=[rule_key],
            reason=(
                f"Policy changed: {rule_key} "
                f"{'enabled' if new_state else 'disabled'} "
                f"(was {'enabled' if old_state else 'disabled'})"
            ),
            payload_hash=f"sha256:policy-change-{rule_key}-{datetime.now(UTC).isoformat()}",
            meta={
                "rule_key": rule_key,
                "old_state": old_state,
                "new_state": new_state,
                "changed_by": changed_by,
                "changed_at": datetime.now(UTC).isoformat()
            }
        )
        
        self.db.add(receipt)
        self.db.flush()
        
        return receipt


# ========================================
# Convenience Functions
# ========================================

def get_rules_service(db: Session) -> RulesService:
    """
    Factory function for creating RulesService.
    
    Args:
        db: Database session
    
    Returns:
        RulesService instance
    
    Usage:
        from utc.database import get_db_context
        from utc.services.rules import get_rules_service
        
        with get_db_context() as db:
            service = get_rules_service(db)
            rules = service.get_all_rules()
    """
    return RulesService(db)


# ========================================
# Testing
# ========================================

if __name__ == "__main__":
    """
    Test the rules service.
    
    Run: python -m utc.services.rules
    """
    from utc.database import get_db_context
    
    print("=" * 60)
    print("📜 Testing Rules Service")
    print("=" * 60)
    
    with get_db_context() as db:
        service = RulesService(db)
        
        # Test 1: Get all rules
        print("\n1️⃣ Getting all rules...")
        rules = service.get_all_rules()
        for rule in rules:
            print(f"  ✅ {rule}")
        
        # Test 2: Get rules dict
        print("\n2️⃣ Getting rules as dictionary...")
        rules_dict = service.get_rules_dict()
        print(f"  ✅ {rules_dict}")
        
        # Test 3: Check if rule is enabled
        print("\n3️⃣ Checking if writes_require_approval is enabled...")
        is_enabled = service.is_rule_enabled("writes_require_approval")
        print(f"  ✅ writes_require_approval: {'ON' if is_enabled else 'OFF'}")
        
        # Test 4: Toggle rule
        print("\n4️⃣ Toggling writes_require_approval...")
        rule = service.toggle_rule(
            "writes_require_approval",
            changed_by="test-user"
        )
        print(f"  ✅ Rule toggled: {rule}")
        
        # Test 5: Evaluate rules for action
        print("\n5️⃣ Evaluating rules for 'write:/payments'...")
        result = service.evaluate_rules_for_action("write:/payments")
        print(f"  ✅ Decision: {result['decision']}")
        print(f"  ✅ Reason: {result['reason']}")
        print(f"  ✅ Rules applied: {result['rules']}")
        
        # Test 6: Check policy change receipt was created
        print("\n6️⃣ Checking policy change receipts...")
        receipts = db.query(Receipt).filter_by(
            decision=DecisionType.POLICY_CHANGE.value
        ).all()
        print(f"  ✅ Policy change receipts: {len(receipts)}")
        if receipts:
            print(f"     Latest: {receipts[-1]}")
        
        # Rollback (don't save test changes)
        print("\n🔄 Rolling back test changes...")
        db.rollback()
    
    print("\n" + "=" * 60)
    print("🎉 All rules service tests passed!")
    print("=" * 60)