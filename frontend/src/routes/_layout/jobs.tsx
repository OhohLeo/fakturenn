import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { Suspense } from "react"

import { JobsService, jobKeys } from "@/hooks/useTreasury"
import { DataTable } from "@/components/Common/DataTable"
import { columns } from "@/components/Jobs/columns"
import PendingJobs from "@/components/Pending/PendingJobs"

function getJobsQueryOptions() {
  return {
    queryFn: () => JobsService.readAllJobs({ skip: 0, limit: 100 }),
    queryKey: jobKeys.lists(),
  }
}

export const Route = createFileRoute("/_layout/jobs")({
  component: Jobs,
  head: () => ({
    meta: [
      {
        title: "Jobs - Fakturenn",
      },
    ],
  }),
})

function JobsTableContent() {
  const { data: jobs } = useSuspenseQuery(getJobsQueryOptions())

  if (jobs.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No jobs found</h3>
        <p className="text-muted-foreground">
          Jobs will appear here when your sources start syncing data
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={jobs.data} />
}

function JobsTable() {
  return (
    <Suspense fallback={<PendingJobs />}>
      <JobsTableContent />
    </Suspense>
  )
}

function Jobs() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Jobs</h1>
          <p className="text-muted-foreground">
            View job history and monitor sync progress
          </p>
        </div>
      </div>
      <JobsTable />
    </div>
  )
}
