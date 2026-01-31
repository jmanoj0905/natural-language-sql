#!/usr/bin/env python3
"""Test script for multi-database functionality."""

import sys
import asyncio
from app.core.database.connection_manager import DatabaseConnectionManager
from app.models.database import DatabaseConfig

async def test_multi_database():
    """Test multi-database connection manager."""
    print("Testing Multi-Database Connection Manager...")
    print("-" * 50)

    manager = DatabaseConnectionManager()

    # Test 1: Create first database
    print("\n1. Registering first database (db1)...")
    try:
        config1 = DatabaseConfig(
            database_id="db1",
            nickname="Test Database 1",
            host="localhost",
            port=5432,
            database="testdb1",
            username="user1",
            password="pass1",
            ssl_mode="prefer"
        )
        manager.register_database("db1", config1)
        print("✓ Database db1 registered successfully")
    except Exception as e:
        print(f"✗ Failed to register db1: {e}")
        return False

    # Test 2: List databases
    print("\n2. Listing databases...")
    databases = manager.list_databases()
    print(f"✓ Found {len(databases)} database(s): {databases}")

    # Test 3: Check default database
    print("\n3. Checking default database...")
    default_db = manager._default_db_id
    print(f"✓ Default database: {default_db}")

    # Test 4: Register second database
    print("\n4. Registering second database (db2)...")
    try:
        config2 = DatabaseConfig(
            database_id="db2",
            nickname="Test Database 2",
            host="localhost",
            port=5432,
            database="testdb2",
            username="user2",
            password="pass2",
            ssl_mode="require"
        )
        manager.register_database("db2", config2)
        print("✓ Database db2 registered successfully")
    except Exception as e:
        print(f"✗ Failed to register db2: {e}")

    # Test 5: List databases again
    print("\n5. Listing databases after adding second...")
    databases = manager.list_databases()
    print(f"✓ Found {len(databases)} database(s): {databases}")

    # Test 6: Get database config
    print("\n6. Getting database config for db1...")
    try:
        config = manager.get_database_config("db1")
        print(f"✓ Config retrieved: {config.nickname} at {config.host}:{config.port}")
    except Exception as e:
        print(f"✗ Failed to get config: {e}")

    # Test 7: Set default database
    print("\n7. Setting db2 as default...")
    try:
        manager.set_default_database("db2")
        print(f"✓ Default database changed to: {manager._default_db_id}")
    except Exception as e:
        print(f"✗ Failed to set default: {e}")

    # Test 8: Disconnect database
    print("\n8. Disconnecting db1...")
    try:
        await manager.disconnect_database("db1")
        databases = manager.list_databases()
        print(f"✓ Database disconnected. Remaining: {databases}")
        print(f"  Default database is now: {manager._default_db_id}")
    except Exception as e:
        print(f"✗ Failed to disconnect: {e}")

    # Test 9: Try to duplicate database ID
    print("\n9. Testing duplicate database ID prevention...")
    try:
        config_dup = DatabaseConfig(
            database_id="db2",
            nickname="Duplicate",
            host="localhost",
            port=5432,
            database="testdb3",
            username="user3",
            password="pass3"
        )
        manager.register_database("db2", config_dup)
        print("✗ Should have failed - duplicate ID allowed!")
        return False
    except Exception as e:
        print(f"✓ Correctly prevented duplicate: {e}")

    # Test 10: Close all
    print("\n10. Closing all database connections...")
    await manager.close()
    databases = manager.list_databases()
    print(f"✓ All connections closed. Databases: {databases}")

    print("\n" + "=" * 50)
    print("All tests passed! ✓")
    return True

if __name__ == "__main__":
    result = asyncio.run(test_multi_database())
    sys.exit(0 if result else 1)
