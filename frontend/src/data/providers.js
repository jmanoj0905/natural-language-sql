// Unified database provider configurations
// Each provider includes database type, display properties, and connection config

export const PROVIDERS = [
  // PostgreSQL Providers
  {
    id: 'localhost-postgres',
    name: 'Localhost',
    dbType: 'postgresql',
    fullName: 'Local PostgreSQL',
    description: 'PostgreSQL on your machine',
    badge: 'Local',
    icon: 'database',
    config: {
      host: 'localhost',
      port: 5432,
      ssl_mode: 'disable'
    },
    hints: {
      database: 'Enter your database name',
      username: 'Usually: postgres',
      password: 'Your PostgreSQL password'
    }
  },
  {
    id: 'docker-postgres',
    name: 'Docker',
    dbType: 'postgresql',
    fullName: 'Docker PostgreSQL',
    description: 'PostgreSQL running in Docker',
    badge: 'Container',
    icon: 'docker',
    config: {
      host: 'localhost',
      port: 5432,
      ssl_mode: 'disable'
    },
    hints: {
      host: 'Use localhost or container name',
      database: 'Database name from docker-compose',
      username: 'Usually: postgres',
      password: 'Password from POSTGRES_PASSWORD env'
    }
  },
  {
    id: 'aws-rds-postgres',
    name: 'AWS RDS',
    dbType: 'postgresql',
    fullName: 'AWS RDS PostgreSQL',
    description: 'Amazon managed PostgreSQL',
    badge: 'Cloud',
    icon: 'aws',
    config: {
      port: 5432,
      ssl_mode: 'require'
    },
    hints: {
      host: 'example.abc123.us-east-1.rds.amazonaws.com',
      database: 'Your database name',
      username: 'Master username from RDS',
      password: 'Master password from RDS'
    }
  },
  {
    id: 'gcp-sql-postgres',
    name: 'Google Cloud SQL',
    dbType: 'postgresql',
    fullName: 'Google Cloud SQL PostgreSQL',
    description: 'GCP managed PostgreSQL',
    badge: 'Cloud',
    icon: 'gcp',
    config: {
      port: 5432,
      ssl_mode: 'require'
    },
    hints: {
      host: 'Use Cloud SQL Proxy or public IP',
      database: 'Your database name',
      username: 'postgres or custom user',
      password: 'User password'
    }
  },
  {
    id: 'azure-postgres',
    name: 'Azure Database',
    dbType: 'postgresql',
    fullName: 'Azure PostgreSQL',
    description: 'Microsoft managed PostgreSQL',
    badge: 'Cloud',
    icon: 'azure',
    config: {
      port: 5432,
      ssl_mode: 'require'
    },
    hints: {
      host: 'servername.postgres.database.azure.com',
      database: 'Your database name',
      username: 'username@servername',
      password: 'Your password'
    }
  },
  {
    id: 'digitalocean-postgres',
    name: 'DigitalOcean',
    dbType: 'postgresql',
    fullName: 'DigitalOcean PostgreSQL',
    description: 'DO managed PostgreSQL',
    badge: 'Cloud',
    icon: 'digitalocean',
    config: {
      port: 25060,
      ssl_mode: 'require'
    },
    hints: {
      host: 'db-postgresql-xxx.ondigitalocean.com',
      database: 'defaultdb or your database',
      username: 'doadmin',
      password: 'From connection details'
    }
  },
  {
    id: 'supabase-postgres',
    name: 'Supabase',
    dbType: 'postgresql',
    fullName: 'Supabase PostgreSQL',
    description: 'Serverless backend platform',
    badge: 'Popular',
    icon: 'supabase',
    config: {
      port: 5432,
      ssl_mode: 'require'
    },
    hints: {
      host: 'db.projectref.supabase.co',
      database: 'postgres',
      username: 'postgres',
      password: 'From project settings'
    }
  },
  {
    id: 'railway-postgres',
    name: 'Railway',
    dbType: 'postgresql',
    fullName: 'Railway PostgreSQL',
    description: 'Railway platform PostgreSQL',
    badge: 'Platform',
    icon: 'railway',
    config: {
      port: 5432,
      ssl_mode: 'require'
    },
    hints: {
      host: 'containers-us-west-xxx.railway.app',
      database: 'railway',
      username: 'postgres',
      password: 'From Railway dashboard'
    }
  },
  {
    id: 'render-postgres',
    name: 'Render',
    dbType: 'postgresql',
    fullName: 'Render PostgreSQL',
    description: 'Render platform PostgreSQL',
    badge: 'Platform',
    icon: 'render',
    config: {
      port: 5432,
      ssl_mode: 'require'
    },
    hints: {
      host: 'dpg-xxxxx.oregon-postgres.render.com',
      database: 'Database name',
      username: 'User from dashboard',
      password: 'From Render dashboard'
    }
  },
  {
    id: 'heroku-postgres',
    name: 'Heroku Postgres',
    dbType: 'postgresql',
    fullName: 'Heroku PostgreSQL',
    description: 'Heroku managed PostgreSQL',
    badge: 'Platform',
    icon: 'heroku',
    config: {
      port: 5432,
      ssl_mode: 'require'
    },
    hints: {
      host: 'ec2-xx-xxx-xxx-xx.compute-1.amazonaws.com',
      database: 'Database name from config',
      username: 'From DATABASE_URL',
      password: 'From DATABASE_URL'
    }
  },
  {
    id: 'neon-postgres',
    name: 'Neon',
    dbType: 'postgresql',
    fullName: 'Neon Serverless PostgreSQL',
    description: 'Serverless PostgreSQL platform',
    badge: 'Serverless',
    icon: 'neon',
    config: {
      port: 5432,
      ssl_mode: 'require'
    },
    hints: {
      host: 'ep-xxx.us-east-2.aws.neon.tech',
      database: 'neondb or your database',
      username: 'From connection string',
      password: 'From connection string'
    }
  },
  {
    id: 'custom-postgres',
    name: 'Custom',
    dbType: 'postgresql',
    fullName: 'Custom PostgreSQL',
    description: 'Manual configuration',
    badge: 'Custom',
    icon: 'settings',
    config: {},
    hints: {}
  },

  // MySQL Providers
  {
    id: 'localhost-mysql',
    name: 'Localhost',
    dbType: 'mysql',
    fullName: 'Local MySQL',
    description: 'MySQL on your machine',
    badge: 'Local',
    icon: 'database',
    config: {
      host: 'localhost',
      port: 3306,
      ssl_mode: 'disable'
    },
    hints: {
      database: 'Enter your database name',
      username: 'Usually: root',
      password: 'Your MySQL password'
    }
  },
  {
    id: 'docker-mysql',
    name: 'Docker',
    dbType: 'mysql',
    fullName: 'Docker MySQL',
    description: 'MySQL running in Docker',
    badge: 'Container',
    icon: 'docker',
    config: {
      host: 'localhost',
      port: 3306,
      ssl_mode: 'disable'
    },
    hints: {
      host: 'Use localhost or container name',
      database: 'Database from MYSQL_DATABASE env',
      username: 'From MYSQL_USER env',
      password: 'From MYSQL_PASSWORD env'
    }
  },
  {
    id: 'aws-rds-mysql',
    name: 'AWS RDS',
    dbType: 'mysql',
    fullName: 'AWS RDS MySQL',
    description: 'Amazon managed MySQL',
    badge: 'Cloud',
    icon: 'aws',
    config: {
      port: 3306,
      ssl_mode: 'require'
    },
    hints: {
      host: 'example.abc123.us-east-1.rds.amazonaws.com',
      database: 'Your database name',
      username: 'Master username from RDS',
      password: 'Master password from RDS'
    }
  },
  {
    id: 'gcp-sql-mysql',
    name: 'Google Cloud SQL',
    dbType: 'mysql',
    fullName: 'Google Cloud SQL MySQL',
    description: 'GCP managed MySQL',
    badge: 'Cloud',
    icon: 'gcp',
    config: {
      port: 3306,
      ssl_mode: 'require'
    },
    hints: {
      host: 'Use Cloud SQL Proxy or public IP',
      database: 'Your database name',
      username: 'root or custom user',
      password: 'User password'
    }
  },
  {
    id: 'azure-mysql',
    name: 'Azure Database',
    dbType: 'mysql',
    fullName: 'Azure MySQL',
    description: 'Microsoft managed MySQL',
    badge: 'Cloud',
    icon: 'azure',
    config: {
      port: 3306,
      ssl_mode: 'require'
    },
    hints: {
      host: 'servername.mysql.database.azure.com',
      database: 'Your database name',
      username: 'username@servername',
      password: 'Your password'
    }
  },
  {
    id: 'digitalocean-mysql',
    name: 'DigitalOcean',
    dbType: 'mysql',
    fullName: 'DigitalOcean MySQL',
    description: 'DO managed MySQL',
    badge: 'Cloud',
    icon: 'digitalocean',
    config: {
      port: 25060,
      ssl_mode: 'require'
    },
    hints: {
      host: 'db-mysql-xxx.ondigitalocean.com',
      database: 'defaultdb or your database',
      username: 'doadmin',
      password: 'From connection details'
    }
  },
  {
    id: 'planetscale-mysql',
    name: 'PlanetScale',
    dbType: 'mysql',
    fullName: 'PlanetScale MySQL',
    description: 'Serverless MySQL platform',
    badge: 'Serverless',
    icon: 'planetscale',
    config: {
      port: 3306,
      ssl_mode: 'require'
    },
    hints: {
      host: 'aws.connect.psdb.cloud',
      database: 'Your database name',
      username: 'From connection string',
      password: 'From connection string'
    }
  },
  {
    id: 'railway-mysql',
    name: 'Railway',
    dbType: 'mysql',
    fullName: 'Railway MySQL',
    description: 'Railway platform MySQL',
    badge: 'Platform',
    icon: 'railway',
    config: {
      port: 3306,
      ssl_mode: 'require'
    },
    hints: {
      host: 'containers-us-west-xxx.railway.app',
      database: 'railway',
      username: 'root',
      password: 'From Railway dashboard'
    }
  },
  {
    id: 'custom-mysql',
    name: 'Custom',
    dbType: 'mysql',
    fullName: 'Custom MySQL',
    description: 'Manual configuration',
    badge: 'Custom',
    icon: 'settings',
    config: {},
    hints: {}
  }
]

// Helper functions
export const getProvidersByType = (dbType) => {
  return PROVIDERS.filter(p => p.dbType === dbType)
}

export const getProviderById = (id) => {
  return PROVIDERS.find(p => p.id === id)
}

export const getAllProviders = () => {
  return PROVIDERS
}
