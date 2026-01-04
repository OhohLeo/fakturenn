import type { ColumnDef } from "@tanstack/react-table"
import { Check, Copy, Loader2 } from "lucide-react"

import type { JobPublic } from "@/client"
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

function formatDateTime(dateString: string | null | undefined) {
  if (!dateString) return "-"
  const date = new Date(dateString)
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function getStatusVariant(
  status: string
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "success":
      return "default"
    case "queued":
      return "secondary"
    case "running":
      return "outline"
    case "failed":
      return "destructive"
    default:
      return "outline"
  }
}

function StatusBadge({ status }: { status: string }) {
  const isRunning = status === "running"

  return (
    <Badge variant={getStatusVariant(status)} className="gap-1">
      {isRunning && <Loader2 className="h-3 w-3 animate-spin" />}
      {status}
    </Badge>
  )
}

export const columns: ColumnDef<JobPublic>[] = [
  {
    accessorKey: "id",
    header: "ID",
    cell: ({ row }) => <CopyId id={row.original.id} />,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <StatusBadge status={row.original.status || "queued"} />,
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
  {
    accessorKey: "scheduled_at",
    header: "Scheduled",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.scheduled_at)}
      </span>
    ),
  },
  {
    accessorKey: "started_at",
    header: "Started",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.started_at)}
      </span>
    ),
  },
]
