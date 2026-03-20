/**
 * Detect write operation type from SQL string.
 * Returns metadata for warning display, or null for SELECT queries.
 */
export function detectWriteOp(sql) {
  if (!sql) return null
  const u = sql.trim().toUpperCase()
  if (u.startsWith('DROP TABLE') || u.startsWith('DROP DATABASE') || u.startsWith('TRUNCATE'))
    return { label: 'DESTRUCTIVE', variant: 'danger', tip: 'This will permanently delete data.' }
  if (u.startsWith('DELETE'))
    return { label: 'DELETE', variant: 'danger', tip: 'This will remove rows from your database.' }
  if (u.startsWith('UPDATE'))
    return { label: 'UPDATE', variant: 'warning', tip: 'This will modify existing rows.' }
  if (u.startsWith('INSERT'))
    return { label: 'INSERT', variant: 'warning', tip: 'This will add new rows to your database.' }
  if (u.startsWith('ALTER'))
    return { label: 'ALTER', variant: 'warning', tip: 'This will change your table structure.' }
  return null
}
