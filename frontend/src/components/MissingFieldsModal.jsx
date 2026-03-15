import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'

export default function MissingFieldsModal({ missingFields, onSubmit, onCancel }) {
  const [fieldValues, setFieldValues] = useState({})

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit(fieldValues)
  }

  const handleChange = (field, value) => {
    setFieldValues(prev => ({
      ...prev,
      [`${field.table}.${field.column}`]: value
    }))
  }

  return (
    <Dialog open={true} onOpenChange={(open) => { if (!open) onCancel() }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <svg className="w-6 h-6 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            ADDITIONAL INFORMATION REQUIRED
          </DialogTitle>
          <DialogDescription>
            The following fields are required but weren't provided in your question
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {missingFields.map((field, index) => (
            <div key={index} className="border-2 border-border rounded-base shadow-shadow p-4 space-y-2">
              <div className="flex items-start justify-between">
                <Label>
                  {field.table}.{field.column}
                  {field.data_type && (
                    <span className="ml-2 text-xs text-foreground/50 font-mono">
                      ({field.data_type})
                    </span>
                  )}
                </Label>
                <Badge className="bg-danger/30">REQUIRED</Badge>
              </div>

              <p className="text-sm text-foreground/70 font-base">
                {field.description}
              </p>

              {field.example && (
                <p className="text-xs text-foreground/50 font-base">
                  Example: <code className="bg-main/20 border-2 border-border rounded-base px-1 font-mono">{field.example}</code>
                </p>
              )}

              <Input
                type="text"
                required
                placeholder={field.example || `Enter ${field.column}...`}
                value={fieldValues[`${field.table}.${field.column}`] || ''}
                onChange={(e) => handleChange(field, e.target.value)}
              />
            </div>
          ))}

          <Alert className="bg-info/20">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <AlertTitle>Why am I seeing this?</AlertTitle>
            <AlertDescription>
              These fields are marked as "NOT NULL" in the database schema and don't have default values.
              You need to provide values for them to create the record successfully.
            </AlertDescription>
          </Alert>

          <DialogFooter>
            <Button variant="neutral" type="button" onClick={onCancel}>CANCEL</Button>
            <Button type="submit" className="flex-1">GENERATE SQL WITH THESE VALUES</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
