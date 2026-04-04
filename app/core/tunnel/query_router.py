"""Query router - routes queries to the correct machine tunnel."""

import uuid
from typing import Optional, Dict, Any

from app.core.tunnel.registry import get_tunnel_registry, DatabaseInfo
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryRouter:
    """Routes database queries to the correct tunnel connection."""

    def __init__(self):
        self._registry = get_tunnel_registry()

    def parse_database_id(
        self, database_id: str
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse database_id into components.
        Format: {machine_id}:{db_type}:{database_name}

        Returns: (machine_id, db_type, database_name)
        """
        parts = database_id.split(":", 2)

        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            # Backwards compatible: machine_id:database_name (db_type defaults to postgresql)
            return parts[0], "postgresql", parts[1]
        elif len(parts) == 1:
            # Direct database name - check if it's a tunnel DB
            return None, None, database_id

        return None, None, None

    def is_tunnel_database(self, database_id: str) -> bool:
        """Check if database_id is a tunnel-based database."""
        machine_id, _, _ = self.parse_database_id(database_id)
        return machine_id is not None

    def get_machine_id(self, database_id: str) -> Optional[str]:
        """Get machine_id from database_id."""
        machine_id, _, _ = self.parse_database_id(database_id)
        return machine_id

    async def route_query(
        self,
        database_id: str,
        sql: str,
        db_type: Optional[str] = None,
        database_name: Optional[str] = None,
        request_type: str = "query",
    ) -> Dict[str, Any]:
        """
        Route a query to the correct machine via tunnel.

        Args:
            database_id: Full database ID (e.g., machine_abc123:postgresql:myapp)
            sql: SQL query to execute
            db_type: Database type (postgresql/mysql) - optional, parsed from database_id
            database_name: Database name - optional, parsed from database_id
            request_type: Type of request - "query" or "schema"

        Returns:
            Dict with query results or error
        """
        # Parse the database_id
        machine_id, parsed_db_type, parsed_db_name = self.parse_database_id(database_id)

        # Use provided values as fallback
        if db_type is None:
            db_type = parsed_db_type or "postgresql"
        if database_name is None:
            database_name = parsed_db_name

        if not machine_id:
            logger.warning("not_a_tunnel_database", database_id=database_id)
            return {
                "success": False,
                "error": "Database is not a tunnel connection",
                "code": "NOT_TUNNEL_DB",
            }

        # Get the target database from machine's DB list
        machine = self._registry.get_machine(machine_id)
        if not machine or not machine.is_connected:
            logger.warning(
                "machine_not_connected", machine_id=machine_id, database_id=database_id
            )
            return {
                "success": False,
                "error": f"Machine {machine_id} is not connected",
                "code": "MACHINE_OFFLINE",
            }

        # Find the target database in the machine's DB list
        target_db = None
        for db in machine.databases:
            if db.name == database_name and (db_type is None or db.db_type == db_type):
                target_db = db
                break

        if not target_db:
            logger.warning(
                "database_not_found_on_machine",
                machine_id=machine_id,
                database=database_name,
            )
            return {
                "success": False,
                "error": f"Database '{database_name}' not found on machine {machine_id}",
                "code": "DB_NOT_FOUND",
            }

        # Generate request ID and send query
        request_id = f"req_{uuid.uuid4().hex[:12]}"

        logger.info(
            "routing_query_to_tunnel",
            request_id=request_id,
            machine_id=machine_id,
            database=database_name,
            sql_preview=sql[:50],
        )

        result = await self._registry.send_query_to_machine(
            machine_id=machine_id,
            request_id=request_id,
            sql=sql,
            database=database_name or "",
            request_type=request_type,
        )

        if result is None:
            return {
                "success": False,
                "error": "Failed to send query to machine",
                "code": "SEND_FAILED",
            }

        return result

    def get_available_databases(self) -> list:
        """Get list of all available tunnel databases."""
        machines = self._registry.get_all_machines()
        databases = []

        for machine in machines:
            for db in machine.databases:
                databases.append(
                    {
                        "database_id": f"{machine.machine_id}:{db.db_type}:{db.name}",
                        "name": db.name,
                        "db_type": db.db_type,
                        "machine_id": machine.machine_id,
                        "host": db.host,
                        "port": db.port,
                        "is_connected": machine.is_connected,
                    }
                )

        return databases


_query_router: Optional[QueryRouter] = None


def get_query_router() -> QueryRouter:
    """Get the global query router instance."""
    global _query_router
    if _query_router is None:
        _query_router = QueryRouter()
    return _query_router
