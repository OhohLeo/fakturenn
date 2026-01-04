import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { Suspense } from "react"

import { WorkflowsService, workflowKeys } from "@/hooks/useTreasury"
import { DataTable } from "@/components/Common/DataTable"
import { AddWorkflow } from "@/components/Workflows/AddWorkflow"
import { columns } from "@/components/Workflows/columns"
import PendingWorkflows from "@/components/Pending/PendingWorkflows"

function getWorkflowsQueryOptions() {
  return {
    queryFn: () => WorkflowsService.readWorkflows({ skip: 0, limit: 100 }),
    queryKey: workflowKeys.lists(),
  }
}

export const Route = createFileRoute("/_layout/workflows")({
  component: Workflows,
  head: () => ({
    meta: [
      {
        title: "Workflows - Fakturenn",
      },
    ],
  }),
})

function WorkflowsTableContent() {
  const { data: workflows } = useSuspenseQuery(getWorkflowsQueryOptions())

  if (workflows.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">
          You don't have any workflows yet
        </h3>
        <p className="text-muted-foreground">
          Create a workflow to organize your data extraction pipeline
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={workflows.data} />
}

function WorkflowsTable() {
  return (
    <Suspense fallback={<PendingWorkflows />}>
      <WorkflowsTableContent />
    </Suspense>
  )
}

function Workflows() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Workflows</h1>
          <p className="text-muted-foreground">
            Create and manage your data extraction workflows
          </p>
        </div>
        <AddWorkflow />
      </div>
      <WorkflowsTable />
    </div>
  )
}
