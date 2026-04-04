# nlsql-connector installation and usage guide

## Quick Install

```bash
cd connector
pip install -e .
```

Or install directly:

```bash
pip install websockets asyncpg aiomysql click
python -m nlsql_connector.tunnel --key YOUR_KEY
```

## Running the Connector

### Step 1: Get a key from the frontend
1. Open NLSQL frontend
2. Click "Connect Local Database" button
3. Copy the generated key (starts with `nlsql_key_`)

### Step 2: Run the connector
```bash
nlsql-connector --key nlsql_key_xxx
```

### Options
| Option | Description |
|--------|-------------|
| `--key, -k` | **Required** - Tunnel key from frontend |
| `--url, -u` | Backend URL (default: https://natural-language-sql-ue9l.onrender.com) |
| `--verbose, -v` | Enable debug output |
| `--no-discover` | Skip database auto-discovery |

## Example Output

```
$ nlsql-connector --key nlsql_key_abc123

Starting nlsql-connector...
Discovering local databases...
Found 2 database(s):
  - myapp (postgresql) at localhost:5432
  - sales (mysql) at localhost:3306
Connected! Machine ID: machine_abc123
Press Ctrl+C to disconnect.
```

## Troubleshooting

### "Failed to connect"
- Check your network connection
- Verify the backend URL is correct
- Make sure the key is valid

### "Registration failed"
- The key may have expired or already been used
- Generate a new key from the frontend

### "No databases discovered"
- Use `--no-discover` to use default config
- Or manually configure in the code