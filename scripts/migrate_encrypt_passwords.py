#!/usr/bin/env python3
"""
Migration script to encrypt existing plaintext database passwords.

This script reads the databases.json file, encrypts all plaintext passwords,
and saves them back to the file. Run this once after upgrading to the version
with password encryption support.

Usage:
    python scripts/migrate_encrypt_passwords.py
"""

import json
import sys
from pathlib import Path
from cryptography.fernet import Fernet
import base64


def get_encryption_key() -> bytes:
    """
    Get encryption key from environment or generate a new one.

    Returns:
        Encryption key as bytes
    """
    import os

    key = os.getenv("DB_ENCRYPTION_KEY")

    if not key:
        print("\n⚠️  WARNING: DB_ENCRYPTION_KEY not set in environment!")
        print("Generating a new key. You MUST save this key to your .env file.")
        key = Fernet.generate_key().decode()
        print(f"\n🔑 Generated Key (add this to your .env file):")
        print(f"DB_ENCRYPTION_KEY={key}\n")

        response = input("Continue with this key? (yes/no): ").strip().lower()
        if response not in ["yes", "y"]:
            print("❌ Migration cancelled.")
            sys.exit(1)

    if isinstance(key, str):
        key = key.encode()

    return key


def is_encrypted(password: str, cipher: Fernet) -> bool:
    """
    Check if a password is already encrypted.

    Args:
        password: Password to check
        cipher: Fernet cipher instance

    Returns:
        True if password is encrypted, False if plaintext
    """
    if not password:
        return True  # Empty passwords don't need encryption

    try:
        encrypted_bytes = base64.b64decode(password.encode())
        cipher.decrypt(encrypted_bytes)
        return True
    except Exception:
        return False


def migrate_passwords(db_config_path: Path, cipher: Fernet, dry_run: bool = False):
    """
    Migrate plaintext passwords to encrypted format.

    Args:
        db_config_path: Path to databases.json file
        cipher: Fernet cipher instance
        dry_run: If True, only show what would be changed without modifying the file
    """
    if not db_config_path.exists():
        print(f"❌ Database config file not found: {db_config_path}")
        print("Nothing to migrate. Run the application first to create the config file.")
        sys.exit(0)

    print(f"📂 Reading config from: {db_config_path}")

    # Load config
    with open(db_config_path, "r") as f:
        data = json.load(f)

    databases = data.get("databases", {})

    if not databases:
        print("✅ No databases configured. Nothing to migrate.")
        sys.exit(0)

    print(f"🔍 Found {len(databases)} database(s)")

    # Check and encrypt passwords
    encrypted_count = 0
    already_encrypted_count = 0

    for db_id, config in databases.items():
        password = config.get("password", "")

        if not password:
            print(f"  ⚪ {db_id}: No password (skipped)")
            continue

        if is_encrypted(password, cipher):
            print(f"  ✅ {db_id}: Already encrypted")
            already_encrypted_count += 1
        else:
            print(f"  🔒 {db_id}: Encrypting plaintext password...")
            encrypted_bytes = cipher.encrypt(password.encode())
            encrypted_password = base64.b64encode(encrypted_bytes).decode()
            config["password"] = encrypted_password
            encrypted_count += 1

    # Save back to file
    if encrypted_count > 0:
        if dry_run:
            print(f"\n🔍 DRY RUN: Would encrypt {encrypted_count} password(s)")
        else:
            # Create backup
            backup_path = db_config_path.with_suffix(".json.backup")
            with open(backup_path, "w") as f:
                json.dump(data, f, indent=2)
            print(f"\n💾 Created backup at: {backup_path}")

            # Save encrypted config
            with open(db_config_path, "w") as f:
                json.dump(data, f, indent=2)

            print(f"✅ Successfully encrypted {encrypted_count} password(s)")
    else:
        print(f"\n✅ All passwords ({already_encrypted_count}) are already encrypted.")

    print("\n🎉 Migration complete!")


def main():
    """Main entry point."""
    print("=" * 70)
    print("Database Password Encryption Migration")
    print("=" * 70)
    print()

    # Get encryption key
    try:
        key = get_encryption_key()
        cipher = Fernet(key)
    except Exception as e:
        print(f"❌ Failed to initialize encryption: {e}")
        sys.exit(1)

    # Determine database config path
    db_config_path = Path.home() / ".nlsql" / "databases.json"

    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("🔍 DRY RUN MODE: No files will be modified\n")

    # Run migration
    try:
        migrate_passwords(db_config_path, cipher, dry_run=dry_run)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
