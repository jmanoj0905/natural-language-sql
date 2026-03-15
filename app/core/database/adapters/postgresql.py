"""PostgreSQL adapter — async connectivity via asyncpg through SQLAlchemy.

All connection parameters are received through the ``config`` object at
call time.  Nothing in this module is hardcoded: host, port, database
name, credentials, and SSL mode all come from ``DatabaseConfig``.
"""

from urllib.parse import quote as _url_quote
from typing import Tuple, Dict

from app.core.database.adapters.base import DatabaseAdapter


class PostgreSQLAdapter(DatabaseAdapter):
    """Builds URLs and introspection queries for PostgreSQL.

    Driver scheme : ``postgresql+asyncpg``
    Default port  : 5432  (set by the caller; this class never assumes it)
    SSL           : appended only when the caller explicitly requests it
                    (anything other than ``"disable"``); omitting the
                    parameter entirely is the asyncpg equivalent of
                    disabling SSL.
    """

    def build_connection_url(self, config) -> str:
        username = _url_quote(config.username, safe="")
        password = _url_quote(config.password, safe="")
        url = (
            f"postgresql+asyncpg://{username}:{password}"
            f"@{config.host}:{config.port}/{config.database}"
        )
        # Only append ?ssl= when the caller actually wants SSL; omitting it
        # is equivalent to 'disable' for asyncpg and avoids a spurious
        # parameter that some connection-string parsers choke on.
        if config.ssl_mode and config.ssl_mode != "disable":
            url += f"?ssl={config.ssl_mode}"
        return url

    def get_schema_name(self, config) -> str:
        return "public"

    def get_size_query(self, config) -> Tuple[str, Dict]:
        return (
            "SELECT pg_size_pretty(pg_database_size(:dbname))",
            {"dbname": config.database},
        )

    def get_connection_count_query(self) -> str:
        return (
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname = current_database()"
        )
