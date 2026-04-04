"""Auto-discover local PostgreSQL and MySQL databases."""

import os
import socket
import asyncio
from dataclasses import dataclass
from typing import List, Optional
import asyncpg
import aiomysql


@dataclass
class DiscoveredDatabase:
    """A discovered database on the local machine."""

    name: str
    db_type: str  # "postgresql" or "mysql"
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


class DatabaseDiscoverer:
    """Discover databases running locally."""

    # Common ports
    POSTGRES_PORTS = [5432, 5433, 5434, 5435]
    MYSQL_PORTS = [3306, 3307, 3308, 3309]

    def __init__(self):
        self.discovered: List[DiscoveredDatabase] = []

    async def discover_all(self) -> List[DiscoveredDatabase]:
        """Discover all local databases."""
        tasks = []

        # Check PostgreSQL on common ports
        for port in self.POSTGRES_PORTS:
            tasks.append(self._check_postgres(port))

        # Check MySQL on common ports
        for port in self.MYSQL_PORTS:
            tasks.append(self._check_mysql(port))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        databases = []
        for result in results:
            if isinstance(result, list):
                databases.extend(result)
            elif isinstance(result, DiscoveredDatabase):
                databases.append(result)

        self.discovered = databases
        return databases

    async def _check_postgres(self, port: int) -> List[DiscoveredDatabase]:
        """Check if PostgreSQL is running on port and return ALL databases."""
        if not await self._is_port_open("localhost", port):
            return []

        try:
            # Try to connect to postgres database
            conn = await asyncpg.connect(
                host="localhost",
                port=port,
                database="postgres",
                user="postgres",
                password="",
                timeout=3,
            )

            # Get list of databases
            rows = await conn.fetch(
                "SELECT datname FROM pg_database WHERE datistemplate = false"
            )
            databases = [row["datname"] for row in rows]
            await conn.close()

            # Return ALL discovered databases, not just the first one
            return [
                DiscoveredDatabase(
                    name=db_name,
                    db_type="postgresql",
                    host="localhost",
                    port=port,
                    username="postgres",
                    password="",
                )
                for db_name in databases
            ]
        except Exception:
            return []

    async def _check_mysql(self, port: int) -> List[DiscoveredDatabase]:
        """Check if MySQL is running on port and return ALL databases."""
        if not await self._is_port_open("localhost", port):
            return []

        try:
            conn = await aiomysql.connect(
                host="localhost",
                port=port,
                user="root",
                password="",
            )

            async with conn.cursor() as cursor:
                await cursor.execute("SHOW DATABASES")
                rows = await cursor.fetchall()
                databases = [
                    row[0]
                    for row in rows
                    if row[0]
                    not in ("information_schema", "performance_schema", "mysql", "sys")
                ]

            conn.close()

            # Return ALL discovered databases
            return [
                DiscoveredDatabase(
                    name=db_name,
                    db_type="mysql",
                    host="localhost",
                    port=port,
                    username="root",
                    password="",
                )
                for db_name in databases
            ]
        except Exception:
            return []

    async def _is_port_open(self, host: str, port: int) -> bool:
        """Check if a port is open."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    def get_databases_for_registration(self) -> List[dict]:
        """Get databases in format for tunnel registration."""
        return [
            {
                "name": db.name,
                "db_type": db.db_type,
                "host": db.host,
                "port": db.port,
            }
            for db in self.discovered
        ]


async def main():
    """Test the discoverer."""
    discoverer = DatabaseDiscoverer()
    dbs = await discoverer.discover_all()

    print(f"Discovered {len(dbs)} databases:")
    for db in dbs:
        print(f"  - {db.name} ({db.db_type}) at {db.host}:{db.port}")


if __name__ == "__main__":
    asyncio.run(main())
