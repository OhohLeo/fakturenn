import type { ColumnDef } from "@tanstack/react-table"
import { Check, Copy, FileText, X } from "lucide-react"
import { Link } from "@tanstack/react-router"

import type { RecordPublic } from "@/client"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"

function CopyId({ id }: { id: string }) {
  const [copiedText, copy] = useCopyToClipboard()
  const isCopied = copiedText === id

  return (
    <div className="flex items-center gap-1.5 group">
      <span className="font-mono text-xs text-muted-foreground">
        {id.slice(0, 8)}...
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="size-6 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={() => copy(id)}
      >
        {isCopied ? (
          <Check className="size-3 text-green-500" />
        ) : (
          <Copy className="size-3" />
        )}
        <span className="sr-only">Copy ID</span>
      </Button>
    </div>
  )
}

function formatDate(dateString: string) {
  const date = new Date(dateString)
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function getStatusVariant(
  status: string
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "success":
    case "exported":
      return "default"
    case "pending":
    case "processing":
      return "secondary"
    case "failed":
      return "destructive"
    default:
      return "outline"
  }
}

export const columns: ColumnDef<RecordPublic>[] = [
  {
    accessorKey: "id",
    header: "ID",
    cell: ({ row }) => <CopyId id={row.original.id} />,
  },
  {
    accessorKey: "date",
    header: "Date",
    cell: ({ row }) => (
      <span className="font-medium">{formatDate(row.original.date)}</span>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge variant={getStatusVariant(row.original.status || "pending")}>
        {row.original.status || "pending"}
      </Badge>
    ),
  },
  {
    accessorKey: "file_path",
    header: "File",
    cell: ({ row }) => {
      const hasFile = !!row.original.file_path
      return (
        <div className="flex items-center gap-1">
          {hasFile ? (
            <>
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Available</span>
            </>
          ) : (
            <>
              <X className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">No file</span>
            </>
          )}
        </div>
      )
    },
  },
  {
    accessorKey: "workflow_id",
    header: "Workflow",
    cell: ({ row }) => (
      <Link
        to="/workflows/$workflowId"
        params={{ workflowId: row.original.workflow_id }}
        className="text-sm text-muted-foreground hover:underline"
      >
        {row.original.workflow_id.slice(0, 8)}...
      </Link>
    ),
  },
  {
    accessorKey: "source_id",
    header: "Source",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground font-mono">
        {row.original.source_id.slice(0, 8)}...
      </span>
    ),
  },
]
