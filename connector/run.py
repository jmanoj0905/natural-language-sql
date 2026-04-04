#!/usr/bin/env python3
"""Simple runner for nlsql-connector."""

import sys
import os

# Add connector directory to path so we can import nlsql_connector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nlsql_connector.tunnel import main

if __name__ == "__main__":
    main()
