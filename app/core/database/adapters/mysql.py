"""MySQL adapter — async connectivity via aiomysql through SQLAlchemy.

All connection parameters are received through the ``config`` object at
call time.  Nothing in this module is hardcoded: host, port, database
name, credentials, and charset all come from ``DatabaseConfig`` or are
driver requirements that are documented inline.
"""

from urllib.parse import quote as _url_quote
from typing import Tuple, Dict

from app.core.database.adapters.base import DatabaseAdapter


class MySQLAdapter(DatabaseAdapter):
    """Builds URLs and introspection queries for MySQL.

    Driver scheme : ``mysql+aiomysql``
    Default port  : 3306  (set by the caller; this class never assumes it)
    charset       : ``utf8mb4`` is always appended.  It is the only MySQL
                    character set that can represent the full Unicode range
                    (including supplementary / emoji characters).  Omitting
                    it causes silent data corruption for any non-BMP text.
    """

    def build_connection_url(self, config) -> str:
        username = _url_quote(config.username, safe="")
        password = _url_quote(config.password, safe="")
        return (
            f"mysql+aiomysql://{username}:{password}"
            f"@{config.host}:{config.port}/{config.database}"
            f"?charset=utf8mb4"
        )

    def get_schema_name(self, config) -> str:
        # In MySQL the schema IS the database.
        return config.database

    def get_size_query(self, config) -> Tuple[str, Dict]:
        return (
            "SELECT COALESCE("
            "  CONCAT(ROUND(SUM(data_length + index_length) / 1024 / 1024, 2), ' MB'), "
            "  '0 MB') "
            "FROM information_schema.tables "
            "WHERE table_schema = :schema_name",
            {"schema_name": config.database},
        )

    def get_connection_count_query(self) -> str:
        return "SELECT COUNT(*) FROM information_schema.processlist"
