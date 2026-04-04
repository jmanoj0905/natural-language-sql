"""nlsql-connector - Connect local databases to NLSQL cloud backend."""

__version__ = "0.1.0"
__author__ = "NLSQL"
__license__ = "MIT"

from nlsql_connector.main import main
from nlsql_connector.discoverer import DatabaseDiscoverer
from nlsql_connector.tunnel import TunnelClient

__all__ = ["main", "DatabaseDiscoverer", "TunnelClient"]
