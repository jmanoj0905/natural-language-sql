import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export default function QueryHistory({ history }) {
  if (!history || history.length === 0) {
    return (
      <Card className="text-center py-12">
        <CardContent>
          <svg className="mx-auto h-12 w-12 text-foreground/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="mt-4 text-lg font-heading text-foreground">NO QUERY HISTORY</h3>
          <p className="mt-2 text-sm text-foreground/60 font-base">
            Your executed queries will appear here
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent>
          <h2 className="text-xl font-heading text-foreground mb-2">QUERY HISTORY</h2>
          <p className="text-sm text-foreground/60 font-base">
            Last {history.length} queries executed
          </p>
        </CardContent>
      </Card>

      {history.map((item) => (
        <Card key={item.id} className="hover:translate-x-boxShadowX hover:translate-y-boxShadowY hover:shadow-none transition-all duration-150">
          <CardContent className="space-y-3">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="text-sm font-heading text-foreground mb-1">
                  {item.question}
                </h3>
                <p className="text-xs text-foreground/50 font-mono">{item.timestamp}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="neutral">{item.rowCount} rows</Badge>
                <span className="text-xs text-foreground/60 font-mono">{item.executionTime.toFixed(2)}ms</span>
              </div>
            </div>

            <div className="bg-black border-2 border-border rounded-base p-3 overflow-x-auto">
              <pre className="text-xs text-success font-mono">{item.sql}</pre>
            </div>

            {item.explanation && (
              <div className="p-3 bg-info/20 border-2 border-border rounded-base">
                <p className="text-xs text-foreground font-base">{item.explanation}</p>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
