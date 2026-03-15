import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

export default function DeleteConfirmDialog({ database, onConfirm, onCancel }) {
  return (
    <Dialog open={true} onOpenChange={(open) => { if (!open) onCancel() }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>DELETE CONNECTION</DialogTitle>
          <DialogDescription>
            Remove <span className="font-heading text-foreground">{database.nickname || database.database_id}</span>?
            This won't affect the actual database, just the saved connection.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="neutral" onClick={onCancel}>CANCEL</Button>
          <Button className="bg-danger" onClick={() => onConfirm(database.database_id)}>DELETE</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
