# nlsql-connector

Connect your local PostgreSQL and MySQL databases to the NLSQL cloud backend.

## Installation

```bash
pip install nlsql-connector
```

Or install from source:

```bash
cd connector
pip install -e .
```

## Usage

1. Open the NLSQL frontend
2. Click "Connect Local Database" 
3. Copy the key shown (e.g., `nlsql_key_xxx`)
4. Run the connector on your machine:

```bash
nlsql-connector --key nlsql_key_xxx
```

### Options

```bash
nlsql-connector --key <key>          # Required: tunnel key from frontend
nlsql-connector --key <key> --url <backend_url>  # Custom backend URL
nlsql-connector --key <key> -v        # Verbose output
nlsql-connector --key <key> --no-discover  # Skip auto-discovery
```

## Example

```bash
$ nlsql-connector --key nlsql_key_abc123

Starting nlsql-connector...
Discovering local databases...
Found 2 database(s):
  - myapp (postgresql) at localhost:5432
  - sales (mysql) at localhost:3306
Connected! Machine ID: machine_abc123
Press Ctrl+C to disconnect.
```

## Requirements

- Python 3.9+
- PostgreSQL and/or MySQL running locally
- Network access to the NLSQL backend

## License

MIT