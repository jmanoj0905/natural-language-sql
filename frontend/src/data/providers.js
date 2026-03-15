// Database provider type definitions
// Each entry defines defaults for a db_type (postgresql, mysql, etc.)

export const DB_TYPES = {
  postgresql: {
    id: 'postgresql',
    label: 'PostgreSQL',
    emoji: '\uD83D\uDC18',
    defaultPort: 5432,
    defaultUsername: 'postgres',
    defaultSslMode: 'disable',
    defaultHost: 'localhost',
  },
  mysql: {
    id: 'mysql',
    label: 'MySQL',
    emoji: '\uD83D\uDC2C',
    defaultPort: 3306,
    defaultUsername: 'root',
    defaultSslMode: 'disable',
    defaultHost: 'localhost',
  },
}

// Ordered list for UI rendering
export const DB_TYPE_LIST = [DB_TYPES.postgresql, DB_TYPES.mysql]

// Helper: get defaults for a db_type
export const getDefaults = (dbType) => {
  const t = DB_TYPES[dbType]
  if (!t) return null
  return {
    db_type: t.id,
    host: t.defaultHost,
    port: t.defaultPort,
    username: t.defaultUsername,
    ssl_mode: t.defaultSslMode,
  }
}

// Helper: get emoji for a db_type
export const getEmoji = (dbType) => DB_TYPES[dbType]?.emoji || '\uD83D\uDDC4\uFE0F'

// Helper: get label for a db_type
export const getLabel = (dbType) => DB_TYPES[dbType]?.label || dbType
