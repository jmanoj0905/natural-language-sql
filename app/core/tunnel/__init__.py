"""Tunnel module for local database connector support."""

from app.core.tunnel.key_manager import (
    TunnelKeyManager,
    get_tunnel_key_manager,
    TunnelKey,
)
from app.core.tunnel.registry import (
    TunnelRegistry,
    get_tunnel_registry,
    MachineConnection,
    DatabaseInfo as TunnelDatabaseInfo,
)
from app.core.tunnel.query_router import QueryRouter, get_query_router

__all__ = [
    "TunnelKeyManager",
    "get_tunnel_key_manager",
    "TunnelKey",
    "TunnelRegistry",
    "get_tunnel_registry",
    "MachineConnection",
    "TunnelDatabaseInfo",
    "QueryRouter",
    "get_query_router",
]
