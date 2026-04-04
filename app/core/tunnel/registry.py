"""Tunnel registry - stores connected machine state and database info."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import WebSocket

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DatabaseInfo:
    """Information about a database discovered by the connector."""

    name: str
    db_type: str  # "postgresql" or "mysql"
    host: str
    port: int
    nickname: Optional[str] = None


@dataclass
class MachineConnection:
    """Represents a connected machine via tunnel."""

    machine_id: str
    key: str
    websocket: Optional[WebSocket] = None
    databases: List[DatabaseInfo] = field(default_factory=list)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    is_connected: bool = True


class TunnelRegistry:
    """Stores and manages connected machines via tunnel."""

    def __init__(self):
        self._machines: Dict[str, MachineConnection] = {}  # machine_id -> connection
        self._key_to_machine: Dict[str, str] = {}  # key -> machine_id
        self._pending_queries: Dict[str, asyncio.Future] = {}  # request_id -> future

    async def register_machine(
        self,
        machine_id: str,
        key: str,
        websocket: WebSocket,
        databases: List[DatabaseInfo],
    ) -> bool:
        """Register a new machine connection."""
        # Check if machine already connected
        if machine_id in self._machines and self._machines[machine_id].is_connected:
            logger.warning("machine_already_connected", machine_id=machine_id)
            # Update existing connection
            existing = self._machines[machine_id]
            existing.websocket = websocket
            existing.last_heartbeat = datetime.utcnow()
            existing.databases = databases
            return True

        connection = MachineConnection(
            machine_id=machine_id,
            key=key,
            websocket=websocket,
            databases=databases,
        )

        self._machines[machine_id] = connection
        self._key_to_machine[key] = machine_id

        logger.info(
            "machine_registered", machine_id=machine_id, db_count=len(databases)
        )
        return True

    async def unregister_machine(self, machine_id: str) -> bool:
        """Unregister a machine (graceful disconnect)."""
        if machine_id in self._machines:
            connection = self._machines[machine_id]
            connection.is_connected = False
            connection.websocket = None

            if connection.key in self._key_to_machine:
                del self._key_to_machine[connection.key]

            logger.info("machine_unregistered", machine_id=machine_id)
            return True
        return False

    async def force_close_machine(self, machine_id: str) -> bool:
        """Force close a machine (invalidate key and remove)."""
        if machine_id in self._machines:
            connection = self._machines[machine_id]

            if connection.key in self._key_to_machine:
                del self._key_to_machine[connection.key]

            del self._machines[machine_id]
            logger.info("machine_force_closed", machine_id=machine_id)
            return True
        return False

    def get_machine(self, machine_id: str) -> Optional[MachineConnection]:
        """Get machine connection by machine_id."""
        return self._machines.get(machine_id)

    def get_machine_by_key(self, key: str) -> Optional[MachineConnection]:
        """Get machine connection by key."""
        machine_id = self._key_to_machine.get(key)
        if machine_id:
            return self._machines.get(machine_id)
        return None

    def get_all_machines(self) -> List[MachineConnection]:
        """Get all connected machines."""
        return [m for m in self._machines.values() if m.is_connected]

    def get_all_machines_with_db(self) -> List[dict]:
        """Get all machines with their database info for frontend."""
        result = []
        for machine in self._machines.values():
            result.append(
                {
                    "machine_id": machine.machine_id,
                    "key": machine.key[:20] + "...",
                    "connected_at": machine.connected_at.isoformat(),
                    "last_heartbeat": machine.last_heartbeat.isoformat(),
                    "is_connected": machine.is_connected,
                    "databases": [
                        {
                            "name": db.name,
                            "db_type": db.db_type,
                            "host": db.host,
                            "port": db.port,
                            "nickname": db.nickname,
                            "database_id": f"{machine.machine_id}:{db.db_type}:{db.name}",
                        }
                        for db in machine.databases
                    ],
                }
            )
        return result

    async def update_heartbeat(self, machine_id: str) -> bool:
        """Update heartbeat for a machine."""
        if machine_id in self._machines:
            self._machines[machine_id].last_heartbeat = datetime.utcnow()
            return True
        return False

    async def update_databases(
        self, machine_id: str, databases: List[DatabaseInfo]
    ) -> bool:
        """Update database list for a machine."""
        if machine_id in self._machines:
            self._machines[machine_id].databases = databases
            logger.info(
                "databases_updated", machine_id=machine_id, db_count=len(databases)
            )
            return True
        return False

    def get_machine_for_database(self, database_id: str) -> Optional[str]:
        """
        Parse database_id and return machine_id.
        Format: {machine_id}:{db_type}:{database_name}
        """
        parts = database_id.split(":", 2)
        if len(parts) >= 1:
            return parts[0]
        return None

    async def send_query_to_machine(
        self,
        machine_id: str,
        request_id: str,
        sql: str,
        database: str,
        request_type: str = "query",
    ) -> Optional[dict]:
        """Send a query to a machine and wait for result."""
        machine = self.get_machine(machine_id)
        if not machine or not machine.is_connected or not machine.websocket:
            logger.warning("machine_not_available", machine_id=machine_id)
            return None

        # Create future for result
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_queries[request_id] = future

        try:
            # Send query request
            await machine.websocket.send_json(
                {
                    "type": "query_request",
                    "request_id": request_id,
                    "sql": sql,
                    "database": database,
                    "request_type": request_type,
                }
            )

            # Wait for result with timeout
            result = await asyncio.wait_for(future, timeout=30.0)
            return result

        except asyncio.TimeoutError:
            logger.error("query_timeout", machine_id=machine_id, request_id=request_id)
            self._pending_queries.pop(request_id, None)
            return {"error": "Query timeout", "code": "TIMEOUT"}
        except Exception as e:
            logger.error(
                "query_failed",
                machine_id=machine_id,
                request_id=request_id,
                error=str(e),
            )
            self._pending_queries.pop(request_id, None)
            return {"error": str(e), "code": "QUERY_FAILED"}

    async def handle_query_result(self, request_id: str, result: dict):
        """Handle query result from a machine."""
        future = self._pending_queries.pop(request_id, None)
        if future and not future.done():
            future.set_result(result)

    def get_stats(self) -> dict:
        """Get registry statistics."""
        connected = sum(1 for m in self._machines.values() if m.is_connected)
        total_dbs = sum(len(m.databases) for m in self._machines.values())

        return {
            "connected_machines": connected,
            "total_databases": total_dbs,
            "pending_queries": len(self._pending_queries),
        }


_tunnel_registry: Optional[TunnelRegistry] = None


def get_tunnel_registry() -> TunnelRegistry:
    """Get the global tunnel registry instance."""
    global _tunnel_registry
    if _tunnel_registry is None:
        _tunnel_registry = TunnelRegistry()
    return _tunnel_registry
