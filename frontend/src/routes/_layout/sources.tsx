import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Database, Search } from "lucide-react"
import { Suspense } from "react"

import { SourcesService, sourceKeys } from "@/hooks/useTreasury"
import type { SourcePublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

function getSourcesQueryOptions() {
  return {
    queryFn: () => SourcesService.readAllSources({ skip: 0, limit: 100 }),
    queryKey: sourceKeys.lists(),
  }
}

export const Route = createFileRoute("/_layout/sources")({
  component: Sources,
  head: () => ({
    meta: [
      {
        title: "Sources - Fakturenn",
      },
    ],
  }),
})

function SourcesTableContent() {
  const { data: sources } = useSuspenseQuery(getSourcesQueryOptions())

  if (sources.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No sources found</h3>
        <p className="text-muted-foreground">
          Sources are created within workflows. Go to a workflow to add sources.
        </p>
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Workflow</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Last Sync</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sources.data.map((source: SourcePublic) => (
          <TableRow key={source.id}>
            <TableCell className="font-medium">{source.name}</TableCell>
            <TableCell>
              <Badge variant="outline">{source.type}</Badge>
            </TableCell>
            <TableCell>
              <Link
                to="/workflows/$workflowId"
                params={{ workflowId: source.workflow_id }}
                className="text-sm text-muted-foreground hover:underline"
              >
                {source.workflow_id.slice(0, 8)}...
              </Link>
            </TableCell>
            <TableCell>
              <Badge variant={source.is_active ? "default" : "secondary"}>
                {source.is_active ? "Active" : "Inactive"}
              </Badge>
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {source.last_sync_at
                ? new Date(source.last_sync_at).toLocaleString()
                : "Never"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function SourcesTableLoading() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  )
}

function Sources() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Database className="h-6 w-6" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Sources</h1>
            <p className="text-muted-foreground">
              All data sources across your workflows
            </p>
          </div>
        </div>
      </div>
      <Suspense fallback={<SourcesTableLoading />}>
        <SourcesTableContent />
      </Suspense>
    </div>
  )
}
