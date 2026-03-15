import { SiPostgresql, SiMysql } from 'react-icons/si'
import { cn } from '@/lib/utils'

const icons = {
  postgresql: SiPostgresql,
  mysql: SiMysql,
}

export default function DbIcon({ dbType, className }) {
  const Icon = icons[dbType]
  if (!Icon) {
    return (
      <svg className={cn('w-4 h-4', className)} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
      </svg>
    )
  }
  return <Icon className={cn('w-4 h-4', className)} />
}
