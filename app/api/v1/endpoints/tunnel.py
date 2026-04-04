"""Tunnel endpoints - REST API + WebSocket for local database connectors."""

import asyncio
import json
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel, Field

from app.core.tunnel.key_manager import get_tunnel_key_manager
from app.core.tunnel.registry import get_tunnel_registry, DatabaseInfo
from app.core.tunnel.query_router import get_query_router
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/tunnel", tags=["tunnel"])


class TunnelKeyResponse(BaseModel):
    """Response for generated tunnel key."""

    key: str
    command: str


class DatabaseInfoRequest(BaseModel):
    """Database info from connector."""

    name: str
    db_type: str = Field(default="postgresql")
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    nickname: Optional[str] = None


class MachineRegisterRequest(BaseModel):
    """Registration request from connector."""

    machine_id: str
    databases: List[DatabaseInfoRequest]


class HeartbeatRequest(BaseModel):
    """Heartbeat request from frontend."""

    key: str


class TunnelStatusResponse(BaseModel):
    """Status of all connected machines."""

    machines: List[dict]
    stats: dict


@router.post("/generate-key", response_model=TunnelKeyResponse)
async def generate_tunnel_key():
    """
    Generate a new tunnel key.

    Frontend calls this to get a key to show the user.
    User then runs nlsql-connector --key <key> on their machine.
    """
    key_manager = get_tunnel_key_manager()
    key = key_manager.generate_key()

    command = f"nlsql-connector --key {key}"

    logger.info("tunnel_key_generated", key_prefix=key[:20] + "...")

    return TunnelKeyResponse(key=key, command=command)


@router.get("/status", response_model=TunnelStatusResponse)
async def get_tunnel_status():
    """Get status of all connected machines."""
    registry = get_tunnel_registry()
    key_manager = get_tunnel_key_manager()

    machines = registry.get_all_machines_with_db()
    stats = key_manager.get_stats()
    registry_stats = registry.get_stats()

    # Merge stats
    stats.update(registry_stats)

    return TunnelStatusResponse(machines=machines, stats=stats)


@router.post("/heartbeat")
async def update_heartbeat(request: HeartbeatRequest):
    """
    Update heartbeat from frontend.

    Called periodically by frontend to indicate user is still active.
    This marks the session as "graceful" - key remains valid after browser close.
    """
    key_manager = get_tunnel_key_manager()

    if not key_manager.validate_key(request.key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Invalid or expired key", "code": "INVALID_KEY"},
        )

    key_manager.update_heartbeat(request.key)

    return {"success": True, "message": "Heartbeat updated"}


@router.post("/disconnect")
async def disconnect_tunnel(request: HeartbeatRequest):
    """
    Graceful disconnect - key remains valid for reconnection.

    Called when user clicks "Disconnect" in the UI.
    """
    key_manager = get_tunnel_key_manager()
    registry = get_tunnel_registry()

    if not key_manager.validate_key(request.key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Invalid or expired key", "code": "INVALID_KEY"},
        )

    machine_id = key_manager.get_machine_id(request.key)
    if machine_id:
        await registry.unregister_machine(machine_id)

    key_manager.graceful_disconnect(request.key)

    logger.info("tunnel_disconnected_gracefully", key=request.key[:20] + "...")

    return {
        "success": True,
        "message": "Disconnected. Key remains valid for reconnection.",
    }


@router.delete("/key/{key}")
async def invalidate_tunnel_key(key: str):
    """
    Invalidate a tunnel key (force close).

    Called when stale connection detected or user wants to force disconnect.
    """
    key_manager = get_tunnel_key_manager()
    registry = get_tunnel_registry()

    machine_id = key_manager.get_machine_id(key)
    if machine_id:
        await registry.force_close_machine(machine_id)

    key_manager.invalidate_key(key)

    logger.info("tunnel_key_invalidated", key=key[:20] + "...")

    return {"success": True, "message": "Key invalidated"}


@router.get("/available-databases")
async def get_available_tunnel_databases():
    """Get list of all available databases from connected tunnel machines."""
    query_router = get_query_router()
    databases = query_router.get_available_databases()

    return {"success": True, "databases": databases}


@router.websocket("/ws")
async def websocket_tunnel(websocket: WebSocket):
    """
    WebSocket endpoint for nlsql-connector.

    Connector connects here to:
    - Register machine with key
    - Send discovered databases
    - Receive query requests
    - Send query results
    """
    await websocket.accept()

    key_manager = get_tunnel_key_manager()
    registry = get_tunnel_registry()

    machine_id = None
    key = None

    try:
        while True:
            # Wait for messages from connector
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                logger.warning("invalid_json_from_connector")
                continue

            msg_type = message.get("type")

            # Handle registration
            if msg_type == "register":
                key = message.get("key")
                machine_id = message.get("machine_id")

                if not key or not machine_id:
                    await websocket.send_json(
                        {"type": "error", "message": "Missing key or machine_id"}
                    )
                    continue

                # Validate and register key
                if not key_manager.register_key(key, machine_id):
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid or already used key"}
                    )
                    continue

                # Parse databases
                db_list = message.get("databases", [])
                databases = []
                for db in db_list:
                    databases.append(
                        DatabaseInfo(
                            name=db.get("name", ""),
                            db_type=db.get("db_type", "postgresql"),
                            host=db.get("host", "localhost"),
                            port=db.get("port", 5432),
                            nickname=db.get("nickname"),
                        )
                    )

                # Register machine
                await registry.register_machine(machine_id, key, websocket, databases)

                await websocket.send_json(
                    {
                        "type": "registered",
                        "machine_id": machine_id,
                        "databases": [
                            {"name": db.name, "db_type": db.db_type} for db in databases
                        ],
                    }
                )

                logger.info(
                    "connector_registered",
                    machine_id=machine_id,
                    db_count=len(databases),
                )

            # Handle heartbeat
            elif msg_type == "heartbeat":
                if machine_id:
                    await registry.update_heartbeat(machine_id)
                    key_manager.update_heartbeat(key)

                    await websocket.send_json({"type": "heartbeat_ack"})

            # Handle database update
            elif msg_type == "databases":
                if machine_id:
                    db_list = message.get("databases", [])
                    databases = []
                    for db in db_list:
                        databases.append(
                            DatabaseInfo(
                                name=db.get("name", ""),
                                db_type=db.get("db_type", "postgresql"),
                                host=db.get("host", "localhost"),
                                port=db.get("port", 5432),
                                nickname=db.get("nickname"),
                            )
                        )

                    await registry.update_databases(machine_id, databases)

                    await websocket.send_json(
                        {"type": "databases_updated", "count": len(databases)}
                    )

            # Handle query result
            elif msg_type == "query_result":
                request_id = message.get("request_id")
                result = message.get("result", {})

                await registry.handle_query_result(request_id, result)

            # Unknown message type
            else:
                logger.warning("unknown_message_type", msg_type=msg_type)

    except WebSocketDisconnect:
        logger.info("connector_disconnected", machine_id=machine_id)

        # On disconnect, mark as disconnected but don't invalidate key
        # Key remains valid for reconnection until force close or timeout
        if machine_id:
            machine = registry.get_machine(machine_id)
            if machine:
                machine.is_connected = False
                machine.websocket = None

    except Exception as e:
        logger.error("websocket_error", machine_id=machine_id, error=str(e))

        if machine_id:
            await registry.force_close_machine(machine_id)

        if key:
            key_manager.invalidate_key(key)
