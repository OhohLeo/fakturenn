import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, Database, FileOutput, Pencil, Trash2 } from "lucide-react"
import { Suspense, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"

import {
  WorkflowsService,
  SourcesService,
  ExportersService,
  workflowKeys,
  sourceKeys,
  exporterKeys,
} from "@/hooks/useTreasury"
import { AddSource } from "@/components/Sources/AddSource"
import { AddExporter } from "@/components/Exporters/AddExporter"
import type { WorkflowPublic, SourcePublic, ExporterPublic } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/workflows_/$workflowId")({
  component: WorkflowDetail,
  head: () => ({
    meta: [
      {
        title: "Workflow Details - Fakturenn",
      },
    ],
  }),
})

function getWorkflowQueryOptions(workflowId: string) {
  return {
    queryFn: () => WorkflowsService.readWorkflow({ id: workflowId }),
    queryKey: workflowKeys.detail(workflowId),
  }
}

function getSourcesQueryOptions(workflowId: string) {
  return {
    queryFn: () => SourcesService.readSources({ workflowId, skip: 0, limit: 100 }),
    queryKey: sourceKeys.byWorkflow(workflowId),
  }
}

function getExportersQueryOptions(workflowId: string) {
  return {
    queryFn: () => ExportersService.readExporters({ workflowId, skip: 0, limit: 100 }),
    queryKey: exporterKeys.byWorkflow(workflowId),
  }
}

const formSchema = z.object({
  name: z.string().min(1, { message: "Name is required" }).max(100),
})

type FormData = z.infer<typeof formSchema>

interface EditWorkflowDialogProps {
  workflow: WorkflowPublic
  isOpen: boolean
  onOpenChange: (open: boolean) => void
}

function EditWorkflowDialog({
  workflow,
  isOpen,
  onOpenChange,
}: EditWorkflowDialogProps) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: {
      name: workflow.name,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      WorkflowsService.updateWorkflow({ id: workflow.id, requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Workflow updated successfully")
      onOpenChange(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.all })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate(data)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>Edit Workflow</DialogTitle>
              <DialogDescription>
                Update the workflow details below.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Name <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="Workflow name" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

interface DeleteWorkflowDialogProps {
  workflow: WorkflowPublic
  isOpen: boolean
  onOpenChange: (open: boolean) => void
}

function DeleteWorkflowDialog({
  workflow,
  isOpen,
  onOpenChange,
}: DeleteWorkflowDialogProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { handleSubmit } = useForm()

  const mutation = useMutation({
    mutationFn: () => WorkflowsService.deleteWorkflow({ id: workflow.id }),
    onSuccess: () => {
      showSuccessToast("Workflow deleted successfully")
      onOpenChange(false)
      navigate({ to: "/workflows" })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.all })
    },
  })

  const onSubmit = () => {
    mutation.mutate()
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Delete Workflow</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{workflow.name}"? This action
              cannot be undone and will also delete all associated sources,
              exporters, records, and jobs.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <LoadingButton
              variant="destructive"
              type="submit"
              loading={mutation.isPending}
            >
              Delete
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function WorkflowHeader({ workflow }: { workflow: WorkflowPublic }) {
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/workflows">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{workflow.name}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:text-destructive"
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <EditWorkflowDialog
        workflow={workflow}
        isOpen={editOpen}
        onOpenChange={setEditOpen}
      />
      <DeleteWorkflowDialog
        workflow={workflow}
        isOpen={deleteOpen}
        onOpenChange={setDeleteOpen}
      />
    </>
  )
}

function SourcesCard({ workflowId, workflowName }: { workflowId: string; workflowName: string }) {
  const { data: sources } = useSuspenseQuery(getSourcesQueryOptions(workflowId))

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            <CardTitle>Sources</CardTitle>
            <Badge variant="secondary">{sources.data.length}</Badge>
          </div>
          <AddSource workflowId={workflowId} workflowName={workflowName} />
        </div>
        <CardDescription>
          Data sources that feed into this workflow
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sources.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No sources configured yet. Add a source to start extracting data.
          </p>
        ) : (
          <div className="space-y-2">
            {sources.data.map((source: SourcePublic) => (
              <div
                key={source.id}
                className="flex items-center justify-between p-2 rounded-md border"
              >
                <div>
                  <p className="font-medium">{source.name}</p>
                  <p className="text-sm text-muted-foreground">
                    Type: {source.type}
                  </p>
                </div>
                <Badge variant={source.is_active ? "default" : "secondary"}>
                  {source.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ExportersCard({ workflowId, workflowName }: { workflowId: string; workflowName: string }) {
  const { data: exporters } = useSuspenseQuery(
    getExportersQueryOptions(workflowId)
  )

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileOutput className="h-5 w-5" />
            <CardTitle>Exporters</CardTitle>
            <Badge variant="secondary">{exporters.data.length}</Badge>
          </div>
          <AddExporter workflowId={workflowId} workflowName={workflowName} />
        </div>
        <CardDescription>
          Export destinations for processed records
        </CardDescription>
      </CardHeader>
      <CardContent>
        {exporters.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No exporters configured yet. Add an exporter to send data to external systems.
          </p>
        ) : (
          <div className="space-y-2">
            {exporters.data.map((exporter: ExporterPublic) => (
              <div
                key={exporter.id}
                className="flex items-center justify-between p-2 rounded-md border"
              >
                <div>
                  <p className="font-medium">{exporter.name}</p>
                  <p className="text-sm text-muted-foreground">
                    Type: {exporter.type}
                  </p>
                </div>
                <Badge variant={exporter.is_active ? "default" : "secondary"}>
                  {exporter.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function WorkflowDetailContent() {
  const { workflowId } = Route.useParams()
  const { data: workflow } = useSuspenseQuery(
    getWorkflowQueryOptions(workflowId)
  )

  return (
    <div className="flex flex-col gap-6">
      <WorkflowHeader workflow={workflow} />

      <div className="grid gap-6 md:grid-cols-2">
        <Suspense
          fallback={
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-4 w-48" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-20 w-full" />
              </CardContent>
            </Card>
          }
        >
          <SourcesCard workflowId={workflowId} workflowName={workflow.name} />
        </Suspense>

        <Suspense
          fallback={
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-4 w-48" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-20 w-full" />
              </CardContent>
            </Card>
          }
        >
          <ExportersCard workflowId={workflowId} workflowName={workflow.name} />
        </Suspense>
      </div>
    </div>
  )
}

function WorkflowDetailLoading() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10" />
        <div>
          <Skeleton className="h-8 w-48 mb-2" />
          <Skeleton className="h-4 w-64" />
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-20 w-full" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-20 w-full" />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function WorkflowDetail() {
  return (
    <Suspense fallback={<WorkflowDetailLoading />}>
      <WorkflowDetailContent />
    </Suspense>
  )
}
