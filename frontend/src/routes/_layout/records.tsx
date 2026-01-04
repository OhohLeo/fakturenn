import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { Suspense } from "react"

import { RecordsService, recordKeys } from "@/hooks/useTreasury"
import { DataTable } from "@/components/Common/DataTable"
import { columns } from "@/components/Records/columns"
import PendingRecords from "@/components/Pending/PendingRecords"

function getRecordsQueryOptions() {
  return {
    queryFn: () => RecordsService.readAllRecords({ skip: 0, limit: 100 }),
    queryKey: recordKeys.lists(),
  }
}

export const Route = createFileRoute("/_layout/records")({
  component: Records,
  head: () => ({
    meta: [
      {
        title: "Records - Fakturenn",
      },
    ],
  }),
})

function RecordsTableContent() {
  const { data: records } = useSuspenseQuery(getRecordsQueryOptions())

  if (records.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No records found</h3>
        <p className="text-muted-foreground">
          Records will appear here once your sources start processing data
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={records.data} />
}

function RecordsTable() {
  return (
    <Suspense fallback={<PendingRecords />}>
      <RecordsTableContent />
    </Suspense>
  )
}

function Records() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Records</h1>
          <p className="text-muted-foreground">
            View all extracted records from your data sources
          </p>
        </div>
      </div>
      <RecordsTable />
    </div>
  )
}
