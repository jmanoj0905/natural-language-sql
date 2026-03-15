import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '@/components/ui/table'

function detectWriteOp(sql) {
  if (!sql) return null
  const u = sql.trim().toUpperCase()
  if (u.startsWith('DROP') || u.startsWith('TRUNCATE'))
    return { label: 'DESTRUCTIVE', variant: 'danger' }
  if (u.startsWith('DELETE')) return { label: 'DELETE', variant: 'danger' }
  if (u.startsWith('UPDATE')) return { label: 'UPDATE', variant: 'warning' }
  if (u.startsWith('INSERT')) return { label: 'INSERT', variant: 'warning' }
  if (u.startsWith('ALTER')) return { label: 'ALTER', variant: 'warning' }
  return null
}

export default function ResultsDisplay({ result }) {
  const [sqlExpanded, setSqlExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  if (!result) return null

  const { generated_sql, sql_explanation, execution_result, metadata } = result
  const writeOp = detectWriteOp(generated_sql)
  const firstRow = execution_result?.rows?.[0]
  const isWriteResult = firstRow?.operation === 'write'

  const handleCopy = () => {
    navigator.clipboard.writeText(generated_sql)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="space-y-4">

      {/* SQL card */}
      <Card className="p-0 gap-0 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b-2 border-border">
          <div className="flex items-center gap-2">
            <span className="text-sm font-heading text-foreground">GENERATED SQL</span>
            {writeOp && (
              <Badge className={
                writeOp.variant === 'danger'
                  ? 'bg-danger/30'
                  : 'bg-warning/30'
              }>
                {writeOp.label}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSqlExpanded(p => !p)}
              className="text-xs text-foreground/50 hover:text-foreground font-heading transition-colors"
            >
              {sqlExpanded ? 'COLLAPSE' : 'EXPAND'}
            </button>
            <button
              onClick={handleCopy}
              className="text-xs text-foreground hover:text-info font-heading transition-colors"
            >
              {copied ? 'COPIED!' : 'COPY'}
            </button>
          </div>
        </div>

        <pre className={`px-4 py-3 text-sm text-success font-mono bg-black overflow-x-auto whitespace-pre-wrap ${
          !sqlExpanded ? 'max-h-32' : ''
        }`}>
          {generated_sql}
        </pre>
      </Card>

      {/* Results card */}
      {execution_result && (
        <Card className="p-0 gap-0 overflow-hidden">
          {/* Results header */}
          <div className="flex items-center justify-between px-4 py-3 border-b-2 border-border">
            <div className="flex items-center gap-2.5">
              <span className="text-sm font-heading text-foreground">RESULTS</span>
              {isWriteResult ? (
                <Badge className="bg-success/30">
                  {firstRow?.affected_rows ?? 0} rows affected
                </Badge>
              ) : (
                <Badge variant="neutral">
                  {execution_result.row_count} {execution_result.row_count === 1 ? 'row' : 'rows'}
                </Badge>
              )}
              <span className="text-xs text-foreground/50 font-mono">
                {(execution_result.execution_time_ms ?? 0).toFixed(1)}ms
              </span>
            </div>
            <span className="flex items-center gap-1.5 text-xs text-success font-heading">
              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              EXECUTED
            </span>
          </div>

          {/* Write op result */}
          {isWriteResult && (
            <div className="px-4 py-6 text-center">
              <Badge className={`px-4 py-2 text-sm ${
                writeOp?.variant === 'danger' ? 'bg-danger/20' : 'bg-success/20'
              }`}>
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                {firstRow?.message ?? 'Operation completed'}
              </Badge>
            </div>
          )}

          {/* Select result table */}
          {!isWriteResult && execution_result.rows?.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow className="bg-main/20">
                  {execution_result.columns.map((col, i) => (
                    <TableHead key={i} className="text-xs uppercase tracking-wider">
                      {col}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {execution_result.rows.map((row, ri) => (
                  <TableRow
                    key={ri}
                    className={`hover:bg-info/10 transition-colors ${ri % 2 === 0 ? 'bg-secondary-background' : 'bg-main/5'}`}
                  >
                    {execution_result.columns.map((col, ci) => {
                      const val = row[col]
                      const isNum = val !== null && !isNaN(Number(val)) && typeof val !== 'boolean'
                      return (
                        <TableCell
                          key={ci}
                          className={`text-sm max-w-xs truncate ${isNum ? 'text-right font-mono tabular-nums' : ''}`}
                        >
                          {val === null ? (
                            <span className="text-foreground/30 italic text-xs">null</span>
                          ) : typeof val === 'boolean' ? (
                            <Badge variant="neutral" className={val ? 'bg-success/30' : 'bg-foreground/10'}>
                              {val ? 'true' : 'false'}
                            </Badge>
                          ) : (
                            String(val)
                          )}
                        </TableCell>
                      )
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Empty result */}
          {!isWriteResult && execution_result.rows?.length === 0 && (
            <div className="py-10 text-center text-foreground/40">
              <svg className="mx-auto h-8 w-8 mb-2 text-foreground/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              <p className="text-sm font-heading">No rows returned</p>
            </div>
          )}

          {/* Explanation */}
          {sql_explanation && (
            <p className="px-5 py-4 text-sm text-foreground leading-relaxed border-t-2 border-border bg-secondary-background font-base">
              {sql_explanation}
            </p>
          )}

          {/* Footer */}
          <div className="flex items-center gap-4 px-5 py-2 bg-main/10 border-t-2 border-border text-xs text-foreground/50 font-mono">
            <span>{metadata?.ai_model}</span>
            <span className="ml-auto">{metadata?.timestamp ? new Date(metadata.timestamp).toLocaleTimeString() : ''}</span>
          </div>
        </Card>
      )}
    </div>
  )
}
