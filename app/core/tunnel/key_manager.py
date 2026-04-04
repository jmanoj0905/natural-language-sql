"""Tunnel key management - generation, validation, and lifecycle."""

import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)

KEY_LENGTH = 32
KEY_PREFIX = "nlsql_key_"
HEARTBEAT_TIMEOUT_SECONDS = 300


@dataclass
class TunnelKey:
    """Represents a tunnel key with its state."""

    key: str
    machine_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    is_assigned: bool = False
    is_invalidated: bool = False


class TunnelKeyManager:
    """Manages tunnel keys for local database connectors."""

    def __init__(self):
        self._keys: Dict[str, TunnelKey] = {}
        self._max_machines = 10

    def generate_key(self) -> str:
        """Generate a new unused tunnel key."""
        while True:
            random_part = secrets.token_urlsafe(KEY_LENGTH)[:KEY_LENGTH]
            key = f"{KEY_PREFIX}{random_part}"
            if key not in self._keys:
                self._keys[key] = TunnelKey(key=key)
                logger.info("tunnel_key_generated", key_prefix=KEY_PREFIX)
                return key

    def register_key(self, key: str, machine_id: str) -> bool:
        """
        Register a key to a machine.
        Returns True if successful, False if key invalid or already assigned.
        """
        if key not in self._keys:
            logger.warning("tunnel_key_not_found", key=key[:20] + "...")
            return False

        tunnel_key = self._keys[key]

        if tunnel_key.is_invalidated:
            logger.warning("tunnel_key_invalidated", key=key[:20] + "...")
            return False

        if tunnel_key.is_assigned and tunnel_key.machine_id != machine_id:
            logger.warning(
                "tunnel_key_already_assigned",
                key=key[:20] + "...",
                machine_id=machine_id,
            )
            return False

        # Check max machines limit
        assigned_count = sum(
            1 for k in self._keys.values() if k.is_assigned and not k.is_invalidated
        )
        if assigned_count >= self._max_machines:
            logger.warning("tunnel_max_machines_reached", max=self._max_machines)
            return False

        tunnel_key.machine_id = machine_id
        tunnel_key.is_assigned = True
        tunnel_key.last_seen = datetime.utcnow()

        logger.info(
            "tunnel_key_registered", key=key[:20] + "...", machine_id=machine_id
        )
        return True

    def validate_key(self, key: str) -> bool:
        """Check if a key is valid and assigned."""
        if key not in self._keys:
            return False
        tunnel_key = self._keys[key]
        return tunnel_key.is_assigned and not tunnel_key.is_invalidated

    def get_machine_id(self, key: str) -> Optional[str]:
        """Get machine_id for a valid key."""
        if key not in self._keys:
            return None
        tunnel_key = self._keys[key]
        if tunnel_key.is_assigned and not tunnel_key.is_invalidated:
            return tunnel_key.machine_id
        return None

    def update_heartbeat(self, key: str) -> bool:
        """Update last_seen timestamp for a key. Returns False if key invalid."""
        if key not in self._keys:
            return False
        tunnel_key = self._keys[key]
        if tunnel_key.is_assigned and not tunnel_key.is_invalidated:
            tunnel_key.last_seen = datetime.utcnow()
            return True
        return False

    def invalidate_key(self, key: str) -> bool:
        """Invalidate a key (force close)."""
        if key not in self._keys:
            return False
        tunnel_key = self._keys[key]
        tunnel_key.is_invalidated = True
        logger.info("tunnel_key_invalidated", key=key[:20] + "...")
        return True

    def graceful_disconnect(self, key: str) -> bool:
        """
        Graceful disconnect - key remains valid for reconnection.
        Returns True if successful.
        """
        if key not in self._keys:
            return False
        tunnel_key = self._keys[key]
        if tunnel_key.is_assigned and not tunnel_key.is_invalidated:
            logger.info("tunnel_key_graceful_disconnect", key=key[:20] + "...")
            return True
        return False

    def get_assigned_machines(self) -> List[str]:
        """Get list of machine_ids with assigned keys."""
        return [
            k.machine_id
            for k in self._keys.values()
            if k.is_assigned and not k.is_invalidated and k.machine_id
        ]

    def cleanup_stale_connections(self) -> List[str]:
        """
        Remove keys with no heartbeat within timeout.
        Returns list of invalidated machine_ids.
        """
        invalidated = []
        timeout = datetime.utcnow() - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)

        for key, tunnel_key in self._keys.items():
            if tunnel_key.is_assigned and not tunnel_key.is_invalidated:
                if tunnel_key.last_seen < timeout:
                    tunnel_key.is_invalidated = True
                    invalidated.append(tunnel_key.machine_id)
                    logger.warning(
                        "tunnel_key_stale_invalidated",
                        key=key[:20] + "...",
                        machine_id=tunnel_key.machine_id,
                    )

        return invalidated

    def get_key_for_machine(self, machine_id: str) -> Optional[str]:
        """Get key for a machine_id."""
        for key, tunnel_key in self._keys.items():
            if (
                tunnel_key.machine_id == machine_id
                and tunnel_key.is_assigned
                and not tunnel_key.is_invalidated
            ):
                return key
        return None

    def get_stats(self) -> Dict:
        """Get tunnel statistics."""
        total = len(self._keys)
        assigned = sum(1 for k in self._keys.values() if k.is_assigned)
        invalidated = sum(1 for k in self._keys.values() if k.is_invalidated)

        return {
            "total_keys": total,
            "assigned_machines": assigned,
            "invalidated": invalidated,
            "available_keys": total - assigned,
            "max_machines": self._max_machines,
        }


_tunnel_key_manager: Optional[TunnelKeyManager] = None


def get_tunnel_key_manager() -> TunnelKeyManager:
    """Get the global tunnel key manager instance."""
    global _tunnel_key_manager
    if _tunnel_key_manager is None:
        _tunnel_key_manager = TunnelKeyManager()
    return _tunnel_key_manager
