"""Test all models together."""

from datetime import datetime, UTC
from utc.models import Base, Rule, Receipt, Event, Feature, create_all_tables, drop_all_tables
from utc.database import engine, get_db_context
from utc.core.constants import DecisionType


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Testing All Models Together")
    print("=" * 60)
    
    # Drop all tables first (clean slate)
    print("\n🗑️  Dropping existing tables (if any)...")
    drop_all_tables(engine)
    print("✅ Tables dropped")
    
    # Create all tables fresh
    print("\n📊 Creating all database tables...")
    create_all_tables(engine)
    print("✅ All tables created!")
    
    with get_db_context() as db:
        # Test Rule
        print("\n1️⃣ Testing Rule model...")
        rule = Rule(key="writes_require_approval", value=1)
        db.add(rule)
        print(f"✅ Created: {rule}")
        
        # Test Receipt (fix datetime.utcnow() deprecation)
        print("\n2️⃣ Testing Receipt model...")
        receipt = Receipt(
            subject="agent-42",
            action="write:/payments",
            decision=DecisionType.ALLOW.value,
            rules=["writes_require_approval"],
            reason="Test receipt",
            payload_hash="sha256:test",
            meta={"lambda_est": 0.2}
        )
        db.add(receipt)
        print(f"✅ Created: {receipt}")
        
        # Test Event (fix datetime.utcnow() deprecation)
        print("\n3️⃣ Testing Event model...")
        event = Event(
            source="test-source",
            event_time=datetime.now(UTC),  # ✅ Fixed deprecation warning!
            topic="test",
            severity="high",
            confidence=0.9,
            entities=["service-A"],
            hash="sha256:test-event",
            summary="Test event summary"
        )
        db.add(event)
        print(f"✅ Created: {event}")
        
        # Test Feature
        print("\n4️⃣ Testing Feature model...")
        feature = Feature(
            unit="route:/payments",
            lambda_est=0.2,
            mu_est=1.0,
            rho=0.2,
            matched_count=5,
            jailbreak_trend="stable"
        )
        db.add(feature)
        print(f"✅ Created: {feature}")
        
        # Commit all
        db.flush()
        
        # Query all
        print("\n5️⃣ Querying all models...")
        rules_count = db.query(Rule).count()
        receipts_count = db.query(Receipt).count()
        events_count = db.query(Event).count()
        features_count = db.query(Feature).count()
        
        print(f"✅ Rules: {rules_count}")
        print(f"✅ Receipts: {receipts_count}")
        print(f"✅ Events: {events_count}")
        print(f"✅ Features: {features_count}")
    
    print("\n" + "=" * 60)
    print("🎉 All models working together successfully!")
    print("=" * 60)
    
    # Show database size
    import os
    db_path = "data/utc.db"
    if os.path.exists(db_path):
        size_kb = os.path.getsize(db_path) / 1024
        print(f"\n📊 Database size: {size_kb:.2f} KB")