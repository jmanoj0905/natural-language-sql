"""Database adapter registry.

Maps the ``db_type`` strings that are persisted in ``DatabaseConfig``
(``"postgresql"``, ``"mysql"``) to the adapter instances that know how
to build connection URLs and run engine-specific introspection queries.

Usage::

    from app.core.database.adapters import get_adapter

    adapter = get_adapter(config.db_type)          # "postgresql" or "mysql"
    url     = adapter.build_connection_url(config) # fully-formed async URL
"""

from app.core.database.adapters.base import DatabaseAdapter
from app.core.database.adapters.postgresql import PostgreSQLAdapter
from app.core.database.adapters.mysql import MySQLAdapter

# One instance per supported engine — stateless, so sharing is safe.
_REGISTRY: dict[str, DatabaseAdapter] = {
    "postgresql": PostgreSQLAdapter(),
    "mysql": MySQLAdapter(),
}


def get_adapter(db_type: str) -> DatabaseAdapter:
    """Return the adapter for *db_type*.

    Args:
        db_type: Value from ``DatabaseConfig.db_type``
                 (e.g. ``"postgresql"``, ``"mysql"``).

    Returns:
        The matching ``DatabaseAdapter`` instance.

    Raises:
        ValueError: If *db_type* is not a supported engine.
    """
    adapter = _REGISTRY.get(db_type.lower())
    if adapter is None:
        raise ValueError(
            f"Unsupported database type: '{db_type}'. "
            f"Supported types: {list(_REGISTRY.keys())}"
        )
    return adapter
