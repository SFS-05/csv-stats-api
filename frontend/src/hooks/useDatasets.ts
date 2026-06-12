/**
 * TanStack Query hooks for dataset operations.
 * Provides typed, cached, and auto-refreshing data fetching.
 */
import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { datasetApi, jobApi } from '@/services/api';

// ── Query keys ────────────────────────────────────────────────────────────────
export const datasetKeys = {
  all: ['datasets'] as const,
  lists: () => [...datasetKeys.all, 'list'] as const,
  list: (page: number, pageSize: number, status?: string) =>
    [...datasetKeys.lists(), { page, pageSize, status }] as const,
  detail: (id: string) => [...datasetKeys.all, 'detail', id] as const,
  schema: (id: string) => [...datasetKeys.all, 'schema', id] as const,
  preview: (id: string, page: number, pageSize: number) =>
    [...datasetKeys.all, 'preview', id, { page, pageSize }] as const,
  profiling: (id: string) => [...datasetKeys.all, 'profiling', id] as const,
};

export const jobKeys = {
  all: ['jobs'] as const,
  detail: (id: string) => [...jobKeys.all, 'detail', id] as const,
};

export function useDatasets(page = 1, pageSize = 20, status?: string) {
  return useQuery({
    queryKey: datasetKeys.list(page, pageSize, status),
    queryFn: () => datasetApi.list(page, pageSize, status),
    staleTime: 30_000,
  });
}

export function useDataset(id: string) {
  return useQuery({
    queryKey: datasetKeys.detail(id),
    queryFn: () => datasetApi.get(id),
    enabled: !!id,
    staleTime: 10_000,
  });
}

export function useDatasetSchema(id: string, enabled = true) {
  return useQuery({
    queryKey: datasetKeys.schema(id),
    queryFn: () => datasetApi.getSchema(id),
    enabled: !!id && enabled,
    staleTime: 60_000,
  });
}

export function useDatasetPreview(
  id: string,
  page = 1,
  pageSize = 50,
  sortBy?: string,
  sortOrder?: 'asc' | 'desc',
  filterCol?: string,
  filterVal?: string
) {
  return useQuery({
    queryKey: datasetKeys.preview(id, page, pageSize),
    queryFn: () =>
      datasetApi.preview(id, page, pageSize, sortBy, sortOrder, filterCol, filterVal),
    enabled: !!id,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}

export function useDatasetProfiling(id: string, enabled = true) {
  return useQuery({
    queryKey: datasetKeys.profiling(id),
    queryFn: () => datasetApi.getProfiling(id),
    enabled: !!id && enabled,
    staleTime: 300_000,
  });
}

export function useUploadDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      name,
      onProgress,
    }: {
      file: File;
      name?: string;
      onProgress?: (pct: number) => void;
    }) => datasetApi.upload(file, name, onProgress),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: datasetKeys.lists() });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => datasetApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: datasetKeys.lists() });
    },
  });
}

export function useJobStatus(jobId: string | null, enabled = true) {
  return useQuery({
    queryKey: jobKeys.detail(jobId ?? ''),
    queryFn: () => jobApi.get(jobId!),
    enabled: !!jobId && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || ['success', 'failure', 'revoked'].includes(status)) {
        return false;
      }
      return 2_000;
    },
  });
}

export function useJobs(page = 1, pageSize = 20, status?: string) {
  return useQuery({
    queryKey: ['jobs', 'list', page, pageSize, status],
    queryFn: () => jobApi.list(page, pageSize, status),
    staleTime: 5_000,
    refetchInterval: 5_000, // Auto refresh jobs list every 5s
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => jobApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}