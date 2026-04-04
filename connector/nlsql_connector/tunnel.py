"""Tunnel client - WebSocket connection to backend."""

import asyncio
import hashlib
import json
import signal
import socket
import sys
from typing import Optional

import websockets
import click

from nlsql_connector.discoverer import DatabaseDiscoverer, DiscoveredDatabase


class TunnelClient:
    """WebSocket client for connecting to NLSQL backend."""

    def __init__(self, backend_url: str, key: str, verbose: bool = False):
        self.backend_url = backend_url.rstrip("/")
        self.key = key
        self.verbose = verbose
        self.machine_id = self._generate_machine_id()
        self.websocket = None
        self.running = False
        self.databases: list = []

        # Database connections cache
        self._db_connections: dict = {}

    def _generate_machine_id(self) -> str:
        """Generate a unique machine ID based on hostname."""
        hostname = hashlib.md5(socket.gethostname().encode()).hexdigest()[:8]
        return f"machine_{hostname}"

    async def connect(self) -> bool:
        """Connect to the backend WebSocket."""
        try:
            self.websocket = await websockets.connect(
                f"{self.backend_url}/ws/tunnel",
                ping_interval=20,
                ping_timeout=10,
            )
            if self.verbose:
                print(f"Connected to {self.backend_url}/ws/tunnel")
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    async def register(self, databases: list) -> bool:
        """Register with the backend."""
        if not self.websocket:
            return False

        self.databases = databases

        message = {
            "type": "register",
            "key": self.key,
            "machine_id": self.machine_id,
            "databases": databases,
        }

        await self.websocket.send(json.dumps(message))

        try:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            data = json.loads(response)

            if data.get("type") == "registered":
                if self.verbose:
                    print(f"Registered successfully. Machine ID: {self.machine_id}")
                    print(f"Databases: {len(databases)}")
                return True
            else:
                print(f"Registration failed: {data.get('message', 'Unknown error')}")
                return False
        except asyncio.TimeoutError:
            print("Registration timeout")
            return False

    async def send_heartbeat(self):
        """Send heartbeat to backend."""
        if self.websocket:
            await self.websocket.send(json.dumps({"type": "heartbeat"}))

    async def send_databases_update(self, databases: list):
        """Update the backend with new database list."""
        if self.websocket:
            await self.websocket.send(
                json.dumps(
                    {
                        "type": "databases",
                        "databases": databases,
                    }
                )
            )

    async def handle_query_request(self, request: dict):
        """Handle incoming query request."""
        request_id = request.get("request_id", "")
        sql = request.get("sql", "")
        database = request.get("database", "")
        request_type = request.get("request_type", "query")

        if self.verbose:
            print(
                f"Request: {request_type} - {sql[:50] if sql else 'N/A'}... on {database}"
            )

        if request_type == "schema":
            result = await self._get_schema(database)
        else:
            result = await self._execute_query(database, sql)

        if self.websocket:
            await self.websocket.send(
                json.dumps(
                    {
                        "type": "query_result",
                        "request_id": request_id,
                        "result": result,
                    }
                )
            )

    async def _get_schema(self, database: str) -> dict:
        """Get database schema."""
        import asyncpg
        import aiomysql

        db_config = None
        for db in self.databases:
            if db["name"] == database:
                db_config = db
                break

        if not db_config:
            return {"success": False, "error": f"Database {database} not found"}

        try:
            if db_config["db_type"] == "postgresql":
                result = await self._get_postgres_schema(db_config)
            elif db_config["db_type"] == "mysql":
                result = await self._get_mysql_schema(db_config)
            else:
                result = {
                    "success": False,
                    "error": f"Unknown db type: {db_config['db_type']}",
                }
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "code": "SCHEMA_ERROR"}

    async def _get_postgres_schema(self, db_config: dict) -> dict:
        """Get PostgreSQL schema."""
        import asyncpg

        cache_key = f"pg_{db_config['host']}_{db_config['port']}_{db_config['name']}"

        try:
            if cache_key not in self._db_connections:
                self._db_connections[cache_key] = await asyncpg.connect(
                    host=db_config["host"],
                    port=db_config["port"],
                    database=db_config["name"],
                    user=db_config.get("username", "postgres"),
                    password=db_config.get("password", ""),
                )

            conn = self._db_connections[cache_key]

            # Get tables
            tables = await conn.fetch("""
                SELECT table_name, table_type 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type IN ('BASE TABLE', 'VIEW')
                ORDER BY table_name
            """)

            schema = {}
            for table in tables:
                table_name = table["table_name"]
                columns = await conn.fetch(
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position
                """,
                    table_name,
                )

                schema[table_name] = {
                    "type": table["table_type"],
                    "columns": [
                        {
                            "name": col["column_name"],
                            "type": col["data_type"],
                            "nullable": col["is_nullable"] == "YES",
                            "default": col["column_default"],
                        }
                        for col in columns
                    ],
                }

            return {"success": True, "schema": schema}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_mysql_schema(self, db_config: dict) -> dict:
        """Get MySQL schema."""
        import aiomysql

        cache_key = f"mysql_{db_config['host']}_{db_config['port']}_{db_config['name']}"

        try:
            if cache_key not in self._db_connections:
                conn = await aiomysql.connect(
                    host=db_config["host"],
                    port=db_config["port"],
                    db=db_config["name"],
                    user=db_config.get("username", "root"),
                    password=db_config.get("password", ""),
                )
                self._db_connections[cache_key] = conn

            conn = self._db_connections[cache_key]
            async with conn.cursor() as cursor:
                await cursor.execute("SHOW TABLES")
                tables = await cursor.fetchall()

                schema = {}
                for (table_name,) in tables:
                    await cursor.execute(f"DESCRIBE `{table_name}`")
                    columns = await cursor.fetchall()

                    schema[table_name] = {
                        "type": "BASE TABLE",
                        "columns": [
                            {
                                "name": col[0],
                                "type": col[1],
                                "nullable": col[2] == "YES",
                                "default": col[4],
                            }
                            for col in columns
                        ],
                    }

                return {"success": True, "schema": schema}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_query(self, database: str, sql: str) -> dict:
        """Execute query on local database."""
        import asyncpg
        import aiomysql

        # Find the database config
        db_config = None
        for db in self.databases:
            if db["name"] == database:
                db_config = db
                break

        if not db_config:
            return {
                "success": False,
                "error": f"Database {database} not found",
                "code": "DB_NOT_FOUND",
            }

        try:
            if db_config["db_type"] == "postgresql":
                result = await self._execute_postgres(db_config, sql)
            elif db_config["db_type"] == "mysql":
                result = await self._execute_mysql(db_config, sql)
            else:
                result = {
                    "success": False,
                    "error": f"Unknown db type: {db_config['db_type']}",
                }

            return result
        except Exception as e:
            return {"success": False, "error": str(e), "code": "QUERY_ERROR"}

    async def _execute_postgres(self, db_config: dict, sql: str) -> dict:
        """Execute PostgreSQL query."""
        import asyncpg

        cache_key = f"pg_{db_config['host']}_{db_config['port']}_{db_config['name']}"

        try:
            if cache_key not in self._db_connections:
                self._db_connections[cache_key] = await asyncpg.connect(
                    host=db_config["host"],
                    port=db_config["port"],
                    database=db_config["name"],
                    user=db_config.get("username", "postgres"),
                    password=db_config.get("password", ""),
                )

            conn = self._db_connections[cache_key]

            # Check if it's a SELECT query
            sql_upper = sql.strip().upper()
            if sql_upper.startswith("SELECT") or sql_upper.startswith("WITH"):
                rows = await conn.fetch(sql)
                columns = list(rows[0].keys()) if rows else []
                return {
                    "success": True,
                    "rows": [dict(row) for row in rows],
                    "columns": columns,
                    "row_count": len(rows),
                }
            else:
                result = await conn.execute(sql)
                return {
                    "success": True,
                    "rows": [{"result": result}],
                    "columns": ["result"],
                    "row_count": 1,
                }
        except Exception as e:
            return {"success": False, "error": str(e), "code": "POSTGRES_ERROR"}

    async def _execute_mysql(self, db_config: dict, sql: str) -> dict:
        """Execute MySQL query."""
        import aiomysql

        cache_key = f"mysql_{db_config['host']}_{db_config['port']}_{db_config['name']}"

        try:
            if cache_key not in self._db_connections:
                conn = await aiomysql.connect(
                    host=db_config["host"],
                    port=db_config["port"],
                    db=db_config["name"],
                    user=db_config.get("username", "root"),
                    password=db_config.get("password", ""),
                )
                self._db_connections[cache_key] = conn

            conn = self._db_connections[cache_key]
            async with conn.cursor() as cursor:
                await cursor.execute(sql)

                sql_upper = sql.strip().upper()
                if sql_upper.startswith("SELECT") or sql_upper.startswith("SHOW"):
                    rows = await cursor.fetchall()
                    columns = (
                        [desc[0] for desc in cursor.description]
                        if cursor.description
                        else []
                    )
                    return {
                        "success": True,
                        "rows": [dict(zip(columns, row)) for row in rows],
                        "columns": columns,
                        "row_count": len(rows),
                    }
                else:
                    await conn.commit()
                    return {
                        "success": True,
                        "rows": [{"affected_rows": cursor.rowcount}],
                        "columns": ["affected_rows"],
                        "row_count": 1,
                    }
        except Exception as e:
            return {"success": False, "error": str(e), "code": "MYSQL_ERROR"}

    async def run(self):
        """Main run loop."""
        self.running = True

        heartbeat_interval = 20
        last_heartbeat = asyncio.get_event_loop().time()

        while self.running:
            try:
                # Use asyncio.wait_for with timeout for receiving messages
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1)
                    data = json.loads(message)

                    msg_type = data.get("type")

                    if msg_type == "query_request":
                        await self.handle_query_request(data)
                    elif msg_type == "heartbeat_ping":
                        if self.verbose:
                            print("Heartbeat ping received")
                    elif msg_type == "disconnect":
                        if self.verbose:
                            print("Server requested disconnect")
                        break

                except asyncio.TimeoutError:
                    pass

                # Send heartbeat periodically
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat >= heartbeat_interval:
                    await self.send_heartbeat()
                    last_heartbeat = current_time
                    if self.verbose:
                        print("Heartbeat sent")

            except websockets.exceptions.ConnectionClosed:
                print("Connection closed by server")
                break
            except Exception as e:
                if self.verbose:
                    print(f"Error: {e}")
                break

        self.running = False

    async def close(self):
        """Close the connection."""
        self.running = False
        if self.websocket:
            await self.websocket.close()

        # Close all database connections
        for conn in self._db_connections.values():
            try:
                await conn.close()
            except:
                pass


async def run_connector(key: str, backend_url: str, verbose: bool, no_discover: bool):
    """Run the connector."""
    print("Starting nlsql-connector...")

    # Discover databases
    databases = []
    if not no_discover:
        print("Discovering local databases...")
        discoverer = DatabaseDiscoverer()
        databases = await discoverer.discover_all()

        if not databases:
            print("No databases discovered. Using default config.")
            databases = [
                {
                    "name": "postgres",
                    "db_type": "postgresql",
                    "host": "localhost",
                    "port": 5432,
                }
            ]

        print(f"Found {len(databases)} database(s):")
        for db in databases:
            if hasattr(db, "name"):  # DiscoveredDatabase object
                print(f"  - {db.name} ({db.db_type}) at {db.host}:{db.port}")
            else:  # dict
                print(
                    f"  - {db.get('name', 'unknown')} ({db.get('db_type', 'unknown')}) at {db.get('host', 'localhost')}:{db.get('port', 5432)}"
                )
    else:
        databases = [
            {
                "name": "postgres",
                "db_type": "postgresql",
                "host": "localhost",
                "port": 5432,
            }
        ]
        print("Auto-discovery disabled. Using defaults.")

    # Connect to backend
    client = TunnelClient(backend_url, key, verbose)

    if not await client.connect():
        print("Failed to connect to backend. Check the URL and try again.")
        return

    if not await client.register(databases):
        print("Failed to register with backend. Check your key.")
        return

    print(f"Connected! Machine ID: {client.machine_id}")
    print("Press Ctrl+C to disconnect.")

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\nShutting down...")
        client.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the client
    try:
        await client.run()
    finally:
        await client.close()

    print("Disconnected.")


@click.command()
@click.option("--key", "-k", required=True, help="Tunnel key from the NLSQL frontend")
@click.option(
    "--url",
    "-u",
    default="https://natural-language-sql-ue9l.onrender.com",
    help="Backend URL",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--no-discover", is_flag=True, help="Skip auto-discovery, use defaults")
def main(key, url, verbose, no_discover):
    """nlsql-connector - Connect local databases to NLSQL cloud."""
    asyncio.run(run_connector(key, url, verbose, no_discover))


if __name__ == "__main__":
    main()
