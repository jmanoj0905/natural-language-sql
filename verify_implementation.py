#!/usr/bin/env python3
"""Verify multi-database implementation structure."""

import os
import re

def check_file_content(filepath, patterns):
    """Check if file contains expected patterns."""
    if not os.path.exists(filepath):
        return False, f"File not found: {filepath}"

    with open(filepath, 'r') as f:
        content = f.read()

    missing = []
    for pattern_name, pattern in patterns.items():
        if not re.search(pattern, content, re.MULTILINE | re.DOTALL):
            missing.append(pattern_name)

    if missing:
        return False, f"Missing: {', '.join(missing)}"

    return True, "All patterns found"

def main():
    print("Verifying Multi-Database Implementation")
    print("=" * 60)

    checks = [
        {
            "file": "app/models/database.py",
            "patterns": {
                "database_id field": r"database_id:\s*str",
                "nickname field": r"nickname:\s*Optional\[str\]",
                "DatabaseInfo model": r"class\s+DatabaseInfo",
                "DatabaseListResponse": r"class\s+DatabaseListResponse"
            }
        },
        {
            "file": "app/core/database/connection_manager.py",
            "patterns": {
                "_engines dict": r"_engines:\s*Dict\[str,\s*AsyncEngine\]",
                "_configs dict": r"_configs:\s*Dict\[str,\s*DatabaseConfig\]",
                "register_database method": r"def\s+register_database",
                "list_databases method": r"def\s+list_databases",
                "get_database_config": r"def\s+get_database_config",
                "disconnect_database": r"async\s+def\s+disconnect_database",
                "set_default_database": r"def\s+set_default_database"
            }
        },
        {
            "file": "app/api/v1/endpoints/database.py",
            "patterns": {
                "GET list endpoint": r'@router\.get\(""',
                "GET database info": r'@router\.get\("\/\{database_id\}"',
                "DELETE database": r'@router\.delete\("\/\{database_id\}"',
                "POST set-default": r'@router\.post\("\/\{database_id\}\/set-default"'
            }
        },
        {
            "file": "app/api/v1/endpoints/query.py",
            "patterns": {
                "database_id parameter": r"database_id:\s*Optional\[str\]\s*=\s*Query",
                "target_db_id variable": r"target_db_id\s*=\s*database_id\s*or"
            }
        },
        {
            "file": "app/core/database/schema_inspector.py",
            "patterns": {
                "_caches dict": r"_caches:\s*Dict\[str,\s*TTLCache\]",
                "get_schema_for_database": r"async\s+def\s+get_schema_for_database",
                "clear_cache_for_database": r"def\s+clear_cache_for_database"
            }
        },
        {
            "file": "frontend/src/components/DatabaseManager.jsx",
            "patterns": {
                "DatabaseManager export": r"export\s+default\s+function\s+DatabaseManager",
                "loadDatabases function": r"const\s+loadDatabases",
                "addDatabase function": r"const\s+addDatabase",
                "removeDatabase function": r"const\s+removeDatabase"
            }
        },
        {
            "file": "frontend/src/App.jsx",
            "patterns": {
                "databases state": r"databases.*setDatabases",
                "DatabaseManager import": r"import\s+DatabaseManager",
                "databases tab": r"id:\s*['\"]databases['\"]",
                "DatabaseManager component": r"<DatabaseManager"
            }
        },
        {
            "file": "frontend/src/components/QueryInterface.jsx",
            "patterns": {
                "databases prop": r"databases\s*=\s*\[\]",
                "selectedDatabases prop": r"selectedDatabases",
                "database selector UI": r"Select\s+Database\s+to\s+Query"
            }
        },
        {
            "file": "frontend/src/components/DatabaseStatus.jsx",
            "patterns": {
                "databases prop": r"databases\s*=\s*\[\]",
                "connectedCount": r"connectedCount",
                "multi-database status": r"getStatusText"
            }
        }
    ]

    passed = 0
    failed = 0

    for check in checks:
        filepath = check["file"]
        print(f"\n{filepath}")
        print("-" * 60)

        success, message = check_file_content(filepath, check["patterns"])

        if success:
            print(f"✓ {message}")
            passed += 1
        else:
            print(f"✗ {message}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n✓ All implementation checks passed!")
        return True
    else:
        print(f"\n✗ {failed} file(s) missing required patterns")
        return False

if __name__ == "__main__":
    import sys
    result = main()
    sys.exit(0 if result else 1)
