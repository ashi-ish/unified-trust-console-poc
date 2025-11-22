"""
Database initialization and seeding.

This script:
- Creates all database tables
- Seeds initial data (the 2 rules from spec)
- Optionally adds sample data for development/testing
- Can reset the database (drop and recreate)

Usage:
    # Initialize with seed data
    python -m utc.database.init_db
    
    # Reset database (drops all tables and recreates)
    python -m utc.database.init_db --reset
    
    # Add sample data for testing
    python -m utc.database.init_db --sample-data
"""

import argparse
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy.exc import IntegrityError

from utc.database.session import engine, get_db_context
from utc.models import create_all_tables, drop_all_tables, Rule, Receipt, Event, Feature
from utc.core.constants import RuleKey, DecisionType


def create_tables(reset: bool = False) -> None:
    """
    Create all database tables.
    
    Args:
        reset: If True, drop existing tables first
    """
    if reset:
        print("🗑️  Dropping existing tables...")
        drop_all_tables(engine)
        print("✅ Tables dropped")
    
    print("📊 Creating database tables...")
    create_all_tables(engine)
    print("✅ Tables created")


def seed_rules() -> None:
    """
    Seed the 2 rules from the PDF specification.
    
    Rules:
    1. writes_require_approval (default: OFF)
    2. read_only_for_risky (default: OFF)
    
    Both rules start disabled (value=0).
    """
    print("\n🌱 Seeding rules...")
    
    rules_to_create = [
        {
            "key": RuleKey.WRITES_REQUIRE_APPROVAL.value,
            "value": 0,  # OFF by default
        },
        {
            "key": RuleKey.READ_ONLY_FOR_RISKY.value,
            "value": 0,  # OFF by default
        },
    ]
    
    with get_db_context() as db:
        for rule_data in rules_to_create:
            # Check if rule already exists
            existing = db.query(Rule).filter_by(key=rule_data["key"]).first()
            
            if existing:
                print(f"  ⏭️  Rule '{rule_data['key']}' already exists (skipping)")
            else:
                rule = Rule(**rule_data)
                db.add(rule)
                print(f"  ✅ Created rule: {rule}")
        
        # Commit is done automatically by get_db_context()
    
    print("✅ Rules seeded")


def seed_sample_data() -> None:
    """
    Seed sample data for development and testing.
    
    This creates:
    - A few sample receipts
    - A few sample events
    - A few sample features
    
    Useful for testing the UI and APIs without manual data entry.
    """
    print("\n🌱 Seeding sample data...")
    
    with get_db_context() as db:
        # Sample Receipts
        print("  📝 Creating sample receipts...")
        sample_receipts = [
            Receipt(
                subject="agent-42",
                action="read:/users",
                decision=DecisionType.ALLOW.value,
                rules=[],
                reason="Read operations are always allowed",
                payload_hash="sha256:sample-read-1",
                meta={"lambda_est": 0.1, "mu_est": 1.0, "rho": 0.1, "unit": "route:/users"}
            ),
            Receipt(
                subject="agent-42",
                action="write:/payments",
                decision=DecisionType.REQUIRE_APPROVAL.value,
                rules=[RuleKey.WRITES_REQUIRE_APPROVAL.value],
                reason="Writes require approval when rule is enabled",
                payload_hash="sha256:sample-write-1",
                meta={"lambda_est": 0.3, "mu_est": 0.5, "rho": 0.6, "unit": "route:/payments"}
            ),
            Receipt(
                subject="agent-99",
                action="write:/admin",
                decision=DecisionType.DENY.value,
                rules=[RuleKey.READ_ONLY_FOR_RISKY.value],
                reason="Read-only mode active for risky units",
                payload_hash="sha256:sample-write-2",
                meta={"lambda_est": 0.8, "mu_est": 0.1, "rho": 8.0, "unit": "route:/admin"}
            ),
        ]
        
        for receipt in sample_receipts:
            try:
                db.add(receipt)
                db.flush()
                print(f"    ✅ {receipt}")
            except IntegrityError:
                db.rollback()
                print(f"    ⏭️  Receipt with hash '{receipt.payload_hash}' already exists")
        
        # Sample Events
        print("  📰 Creating sample events...")
        sample_events = [
            Event(
                source="nvd.nist.gov",
                event_time=datetime.now(UTC),
                topic="cve",
                severity="critical",
                confidence=0.95,
                entities=["openssl", "tls"],
                hash="sha256:sample-event-1",
                link="https://nvd.nist.gov/vuln/detail/CVE-2024-0001",
                summary="Critical TLS vulnerability discovered in OpenSSL 3.x"
            ),
            Event(
                source="security-team",
                event_time=datetime.now(UTC),
                topic="incident",
                severity="high",
                confidence=1.0,
                entities=["api-gateway", "auth"],
                hash="sha256:sample-event-2",
                link=None,
                summary="Multiple failed authentication attempts detected on API gateway"
            ),
            Event(
                source="threat-intel",
                event_time=datetime.now(UTC),
                topic="threat",
                severity="medium",
                confidence=0.7,
                entities=["payments", "fraud"],
                hash="sha256:sample-event-3",
                link="https://example.com/threat-report",
                summary="Increased fraud activity observed in payment processing"
            ),
        ]
        
        for event in sample_events:
            try:
                db.add(event)
                db.flush()
                print(f"    ✅ {event}")
            except IntegrityError:
                db.rollback()
                print(f"    ⏭️  Event with hash '{event.hash}' already exists")
        
        # Sample Features
        print("  📊 Creating sample features...")
        sample_features = [
            Feature(
                unit="route:/users",
                lambda_est=0.1,
                mu_est=1.0,
                rho=0.1,
                matched_count=2,
                jailbreak_trend="stable"
            ),
            Feature(
                unit="route:/payments",
                lambda_est=0.6,
                mu_est=1.0,
                rho=0.6,
                matched_count=8,
                jailbreak_trend="rising"
            ),
            Feature(
                unit="route:/admin",
                lambda_est=0.95,
                mu_est=0.1,
                rho=9.5,  # Over 1.0! System overloaded
                matched_count=25,
                jailbreak_trend="critical"
            ),
        ]
        
        for feature in sample_features:
            db.add(feature)
            db.flush()
            print(f"    ✅ {feature}")
        
    print("✅ Sample data seeded")


def print_database_status() -> None:
    """Print current database status and counts."""
    print("\n" + "=" * 60)
    print("📊 Database Status")
    print("=" * 60)
    
    with get_db_context() as db:
        rules_count = db.query(Rule).count()
        receipts_count = db.query(Receipt).count()
        events_count = db.query(Event).count()
        features_count = db.query(Feature).count()
        
        print(f"  Rules:    {rules_count}")
        print(f"  Receipts: {receipts_count}")
        print(f"  Events:   {events_count}")
        print(f"  Features: {features_count}")
        
        # Show the rules
        if rules_count > 0:
            print("\n  Current Rules:")
            rules = db.query(Rule).all()
            for rule in rules:
                print(f"    • {rule}")
    
    print("=" * 60)


def initialize_database(reset: bool = False, sample_data: bool = False) -> None:
    """
    Initialize the database.
    
    Args:
        reset: Drop existing tables before creating
        sample_data: Add sample data for testing
    """
    print("=" * 60)
    print("🗄️  Database Initialization")
    print("=" * 60)
    
    # Step 1: Create tables
    create_tables(reset=reset)
    
    # Step 2: Seed rules (always)
    seed_rules()
    
    # Step 3: Seed sample data (optional)
    if sample_data:
        seed_sample_data()
    
    # Step 4: Show status
    print_database_status()
    
    print("\n✅ Database initialization complete!")


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Initialize and seed the Unified Trust Console database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize with just the 2 rules
  python -m utc.database.init_db
  
  # Reset database (drop all tables and recreate)
  python -m utc.database.init_db --reset
  
  # Add sample data for testing
  python -m utc.database.init_db --sample-data
  
  # Full reset with sample data
  python -m utc.database.init_db --reset --sample-data
        """
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing tables before creating (WARNING: deletes all data!)"
    )
    
    parser.add_argument(
        "--sample-data",
        action="store_true",
        help="Add sample data for development/testing"
    )
    
    args = parser.parse_args()
    
    # Confirm reset if requested
    if args.reset:
        print("⚠️  WARNING: This will DELETE ALL DATA in the database!")
        response = input("Are you sure? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            print("❌ Aborted")
            return
    
    # Initialize
    initialize_database(reset=args.reset, sample_data=args.sample_data)


if __name__ == "__main__":
    main()