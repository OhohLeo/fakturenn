import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { FileOutput, Search } from "lucide-react"
import { Suspense } from "react"

import { ExportersService, exporterKeys } from "@/hooks/useTreasury"
import type { ExporterPublic } from "@/client"
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

function getExportersQueryOptions() {
  return {
    queryFn: () => ExportersService.readAllExporters({ skip: 0, limit: 100 }),
    queryKey: exporterKeys.lists(),
  }
}

export const Route = createFileRoute("/_layout/exporters")({
  component: Exporters,
  head: () => ({
    meta: [
      {
        title: "Exporters - Fakturenn",
      },
    ],
  }),
})

function ExportersTableContent() {
  const { data: exporters } = useSuspenseQuery(getExportersQueryOptions())

  if (exporters.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No exporters found</h3>
        <p className="text-muted-foreground">
          Exporters are created within workflows. Go to a workflow to add exporters.
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
        </TableRow>
      </TableHeader>
      <TableBody>
        {exporters.data.map((exporter: ExporterPublic) => (
          <TableRow key={exporter.id}>
            <TableCell className="font-medium">{exporter.name}</TableCell>
            <TableCell>
              <Badge variant="outline">{exporter.type}</Badge>
            </TableCell>
            <TableCell>
              <Link
                to="/workflows/$workflowId"
                params={{ workflowId: exporter.workflow_id }}
                className="text-sm text-muted-foreground hover:underline"
              >
                {exporter.workflow_id.slice(0, 8)}...
              </Link>
            </TableCell>
            <TableCell>
              <Badge variant={exporter.is_active ? "default" : "secondary"}>
                {exporter.is_active ? "Active" : "Inactive"}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function ExportersTableLoading() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  )
}

function Exporters() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileOutput className="h-6 w-6" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Exporters</h1>
            <p className="text-muted-foreground">
              All export destinations across your workflows
            </p>
          </div>
        </div>
      </div>
      <Suspense fallback={<ExportersTableLoading />}>
        <ExportersTableContent />
      </Suspense>
    </div>
  )
}
