"""Abstract base class for database-engine adapters.

Every method that is specific to one database engine lives here as an
abstract contract.  Concrete subclasses (PostgreSQLAdapter, MySQLAdapter)
supply the implementations.  Nothing in this file is engine-specific or
hardcoded — all runtime values arrive through the DatabaseConfig that the
caller passes in.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict


class DatabaseAdapter(ABC):
    """One instance per supported database engine.

    ``config`` in every signature below is a ``DatabaseConfig`` instance
    (see ``app.models.database``).  It is duck-typed here so that the
    adapters have zero imports from the rest of the application.
    """

    # ------------------------------------------------------------------
    # Connection URL
    # ------------------------------------------------------------------

    @abstractmethod
    def build_connection_url(self, config) -> str:
        """Return the full SQLAlchemy async connection URL.

        The URL must include the correct async driver scheme
        (e.g. ``postgresql+asyncpg``, ``mysql+aiomysql``) and any
        driver-required query-string parameters (e.g. ``charset``).
        Username and password must be URL-encoded so that special
        characters do not break URL parsing.
        """

    # ------------------------------------------------------------------
    # Schema / introspection helpers
    # ------------------------------------------------------------------

    @abstractmethod
    def get_schema_name(self, config) -> str:
        """Return the schema name to use in ``information_schema`` queries.

        PostgreSQL exposes user tables under the ``public`` schema;
        MySQL uses the database name itself as the schema.
        """

    @abstractmethod
    def get_size_query(self, config) -> Tuple[str, Dict]:
        """Return ``(sql_text, bound_params)`` that yields a human-readable
        database-size string (e.g. ``"42 MB"``).
        """

    @abstractmethod
    def get_connection_count_query(self) -> str:
        """Return SQL that yields the current active-connection count as a
        single integer row.
        """
