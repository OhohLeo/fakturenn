/**
 * TanStack Query hooks for Treasury API endpoints.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ExportersService,
  JobsService,
  RecordsService,
  SchemasService,
  SourcesService,
  WorkflowsService,
  type ExporterCreate,
  type ExporterUpdate,
  type MapperCreate,
  type MapperUpdate,
  type ParserCreate,
  type ParserUpdate,
  type SourceCreate,
  type SourceUpdate,
  type WorkflowCreate,
  type WorkflowUpdate,
} from "@/client";
import useCustomToast from "./useCustomToast";

// Re-export services for direct usage
export {
  ExportersService,
  JobsService,
  RecordsService,
  SchemasService,
  SourcesService,
  WorkflowsService,
};

// Query keys
export const workflowKeys = {
  all: ["workflows"] as const,
  lists: () => [...workflowKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) => [...workflowKeys.lists(), filters] as const,
  details: () => [...workflowKeys.all, "detail"] as const,
  detail: (id: string) => [...workflowKeys.details(), id] as const,
};

export const sourceKeys = {
  all: ["sources"] as const,
  lists: () => [...sourceKeys.all, "list"] as const,
  listByWorkflow: (workflowId: string) => [...sourceKeys.lists(), { workflowId }] as const,
  byWorkflow: (workflowId: string) => [...sourceKeys.lists(), { workflowId }] as const,
  details: () => [...sourceKeys.all, "detail"] as const,
  detail: (id: string) => [...sourceKeys.details(), id] as const,
};

export const parserKeys = {
  all: ["parsers"] as const,
  lists: () => [...parserKeys.all, "list"] as const,
  listBySource: (sourceId: string) => [...parserKeys.lists(), { sourceId }] as const,
};

export const exporterKeys = {
  all: ["exporters"] as const,
  lists: () => [...exporterKeys.all, "list"] as const,
  listByWorkflow: (workflowId: string) => [...exporterKeys.lists(), { workflowId }] as const,
  byWorkflow: (workflowId: string) => [...exporterKeys.lists(), { workflowId }] as const,
  details: () => [...exporterKeys.all, "detail"] as const,
  detail: (id: string) => [...exporterKeys.details(), id] as const,
};

export const mapperKeys = {
  all: ["mappers"] as const,
  lists: () => [...mapperKeys.all, "list"] as const,
  listByExporter: (exporterId: string) => [...mapperKeys.lists(), { exporterId }] as const,
};

export const recordKeys = {
  all: ["records"] as const,
  lists: () => [...recordKeys.all, "list"] as const,
  listByWorkflow: (workflowId: string, status?: string) => [...recordKeys.lists(), { workflowId, status }] as const,
  listBySource: (sourceId: string, status?: string) => [...recordKeys.lists(), { sourceId, status }] as const,
  details: () => [...recordKeys.all, "detail"] as const,
  detail: (id: string) => [...recordKeys.details(), id] as const,
};

export const jobKeys = {
  all: ["jobs"] as const,
  lists: () => [...jobKeys.all, "list"] as const,
  listByWorkflow: (workflowId: string, status?: string) => [...jobKeys.lists(), { workflowId, status }] as const,
  listBySource: (sourceId: string, status?: string) => [...jobKeys.lists(), { sourceId, status }] as const,
  details: () => [...jobKeys.all, "detail"] as const,
  detail: (id: string) => [...jobKeys.details(), id] as const,
};

// Workflow hooks

export function useWorkflows(skip = 0, limit = 100) {
  return useQuery({
    queryKey: workflowKeys.list({ skip, limit }),
    queryFn: () => WorkflowsService.readWorkflows({ skip, limit }),
  });
}

export function useWorkflow(id: string) {
  return useQuery({
    queryKey: workflowKeys.detail(id),
    queryFn: () => WorkflowsService.readWorkflow({ id }),
    enabled: !!id,
  });
}

export function useCreateWorkflow() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: (data: WorkflowCreate) =>
      WorkflowsService.createWorkflow({ requestBody: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() });
      showSuccessToast("Workflow created successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useUpdateWorkflow() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WorkflowUpdate }) =>
      WorkflowsService.updateWorkflow({ id, requestBody: data }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() });
      queryClient.invalidateQueries({ queryKey: workflowKeys.detail(variables.id) });
      showSuccessToast("Workflow updated successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: (id: string) => WorkflowsService.deleteWorkflow({ id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() });
      showSuccessToast("Workflow deleted successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

// Source hooks

export function useSources(workflowId: string, skip = 0, limit = 100) {
  return useQuery({
    queryKey: sourceKeys.listByWorkflow(workflowId),
    queryFn: () => SourcesService.readSources({ workflowId, skip, limit }),
    enabled: !!workflowId,
  });
}

export function useSource(id: string) {
  return useQuery({
    queryKey: sourceKeys.detail(id),
    queryFn: () => SourcesService.readSource({ id }),
    enabled: !!id,
  });
}

export function useCreateSource() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ workflowId, data }: { workflowId: string; data: SourceCreate }) =>
      SourcesService.createSource({ workflowId, requestBody: data }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.listByWorkflow(variables.workflowId) });
      showSuccessToast("Source created successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useUpdateSource() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SourceUpdate }) =>
      SourcesService.updateSource({ id, requestBody: data }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
      queryClient.invalidateQueries({ queryKey: sourceKeys.detail(variables.id) });
      showSuccessToast("Source updated successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useDeleteSource() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: (id: string) => SourcesService.deleteSource({ id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
      showSuccessToast("Source deleted successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useTriggerJob() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: (sourceId: string) => JobsService.triggerJob({ sourceId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: jobKeys.lists() });
      showSuccessToast("Job triggered successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

// Parser hooks (parsers are nested under SourcesService)

export function useParsers(sourceId: string, skip = 0, limit = 100) {
  return useQuery({
    queryKey: parserKeys.listBySource(sourceId),
    queryFn: () => SourcesService.readParsers({ sourceId, skip, limit }),
    enabled: !!sourceId,
  });
}

export function useCreateParser() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ sourceId, data }: { sourceId: string; data: ParserCreate }) =>
      SourcesService.createParser({ sourceId, requestBody: data }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: parserKeys.listBySource(variables.sourceId) });
      showSuccessToast("Parser created successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useUpdateParser() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ sourceId, parserId, data }: { sourceId: string; parserId: string; data: ParserUpdate }) =>
      SourcesService.updateParser({ sourceId, parserId, requestBody: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: parserKeys.lists() });
      showSuccessToast("Parser updated successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useDeleteParser() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ sourceId, parserId }: { sourceId: string; parserId: string }) =>
      SourcesService.deleteParser({ sourceId, parserId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: parserKeys.lists() });
      showSuccessToast("Parser deleted successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

// Exporter hooks

export function useExporters(workflowId: string, skip = 0, limit = 100) {
  return useQuery({
    queryKey: exporterKeys.listByWorkflow(workflowId),
    queryFn: () => ExportersService.readExporters({ workflowId, skip, limit }),
    enabled: !!workflowId,
  });
}

export function useExporter(id: string) {
  return useQuery({
    queryKey: exporterKeys.detail(id),
    queryFn: () => ExportersService.readExporter({ id }),
    enabled: !!id,
  });
}

export function useCreateExporter() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ workflowId, data }: { workflowId: string; data: ExporterCreate }) =>
      ExportersService.createExporter({ workflowId, requestBody: data }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: exporterKeys.listByWorkflow(variables.workflowId) });
      showSuccessToast("Exporter created successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useUpdateExporter() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ExporterUpdate }) =>
      ExportersService.updateExporter({ id, requestBody: data }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: exporterKeys.lists() });
      queryClient.invalidateQueries({ queryKey: exporterKeys.detail(variables.id) });
      showSuccessToast("Exporter updated successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useDeleteExporter() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: (id: string) => ExportersService.deleteExporter({ id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: exporterKeys.lists() });
      showSuccessToast("Exporter deleted successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

// Mapper hooks (mappers are nested under ExportersService)

export function useMappers(exporterId: string, skip = 0, limit = 100) {
  return useQuery({
    queryKey: mapperKeys.listByExporter(exporterId),
    queryFn: () => ExportersService.readMappers({ exporterId, skip, limit }),
    enabled: !!exporterId,
  });
}

export function useCreateMapper() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ exporterId, data }: { exporterId: string; data: MapperCreate }) =>
      ExportersService.createMapper({ exporterId, requestBody: data }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: mapperKeys.listByExporter(variables.exporterId) });
      showSuccessToast("Mapper created successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useUpdateMapper() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ exporterId, mapperId, data }: { exporterId: string; mapperId: string; data: MapperUpdate }) =>
      ExportersService.updateMapper({ exporterId, mapperId, requestBody: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: mapperKeys.lists() });
      showSuccessToast("Mapper updated successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

export function useDeleteMapper() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: ({ exporterId, mapperId }: { exporterId: string; mapperId: string }) =>
      ExportersService.deleteMapper({ exporterId, mapperId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: mapperKeys.lists() });
      showSuccessToast("Mapper deleted successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

// Record hooks

export function useRecordsByWorkflow(workflowId: string, status?: string, skip = 0, limit = 100) {
  return useQuery({
    queryKey: recordKeys.listByWorkflow(workflowId, status),
    queryFn: () => RecordsService.readRecordsByWorkflow({
      workflowId,
      status: status as "pending" | "processing" | "success" | "failed" | "exported" | undefined,
      skip,
      limit
    }),
    enabled: !!workflowId,
  });
}

export function useRecordsBySource(sourceId: string, status?: string, skip = 0, limit = 100) {
  return useQuery({
    queryKey: recordKeys.listBySource(sourceId, status),
    queryFn: () => RecordsService.readRecordsBySource({
      sourceId,
      status: status as "pending" | "processing" | "success" | "failed" | "exported" | undefined,
      skip,
      limit
    }),
    enabled: !!sourceId,
  });
}

export function useRecord(id: string) {
  return useQuery({
    queryKey: recordKeys.detail(id),
    queryFn: () => RecordsService.readRecord({ id }),
    enabled: !!id,
  });
}

// Note: Export triggering is not yet implemented in the API
// When available, add useTriggerExport hook here

export function useDeleteRecord() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useCustomToast();

  return useMutation({
    mutationFn: (id: string) => RecordsService.deleteRecord({ id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: recordKeys.lists() });
      showSuccessToast("Record deleted successfully");
    },
    onError: (error: Error) => {
      showErrorToast(error.message);
    },
  });
}

// Job hooks

export function useJobsByWorkflow(workflowId: string, status?: string, skip = 0, limit = 100) {
  return useQuery({
    queryKey: jobKeys.listByWorkflow(workflowId, status),
    queryFn: () => JobsService.readJobsByWorkflow({
      workflowId,
      status: status as "queued" | "running" | "success" | "failed" | undefined,
      skip,
      limit
    }),
    enabled: !!workflowId,
  });
}

export function useJobsBySource(sourceId: string, status?: string, skip = 0, limit = 100) {
  return useQuery({
    queryKey: jobKeys.listBySource(sourceId, status),
    queryFn: () => JobsService.readJobsBySource({
      sourceId,
      status: status as "queued" | "running" | "success" | "failed" | undefined,
      skip,
      limit
    }),
    enabled: !!sourceId,
  });
}

export function useJob(id: string) {
  return useQuery({
    queryKey: jobKeys.detail(id),
    queryFn: () => JobsService.readJob({ id }),
    enabled: !!id,
  });
}

// Schema hooks

export function useSchema(entityType: string, providerType: string) {
  return useQuery({
    queryKey: ["schemas", entityType, providerType],
    queryFn: () => SchemasService.getSchema({ entityType, providerType }),
    enabled: !!entityType && !!providerType,
  });
}

export function useSchemasList() {
  return useQuery({
    queryKey: ["schemas"],
    queryFn: () => SchemasService.listSchemas(),
  });
}
