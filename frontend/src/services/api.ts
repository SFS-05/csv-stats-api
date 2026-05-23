/**
 * Typed API client using axios.
 * All requests go through this module — no raw fetch() calls in components.
 */
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import type {
  AISummary,
  AIRecommendations,
  BarChartData,
  BoxPlotData,
  ChatMessage,
  CorrelationData,
  Dataset,
  DatasetListItem,
  DatasetProfiling,
  DatasetPreview,
  DatasetSchema,
  HistogramData,
  Job,
  LoginRequest,
  PaginatedResponse,
  RegisterRequest,
  TokenResponse,
  UploadResult,
  User,
} from '@/types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// ── Axios instance ────────────────────────────────────────────────────────────
const apiClient: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 60_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Auth token injection ──────────────────────────────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Token refresh on 401 ──────────────────────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const { data } = await axios.post<TokenResponse>(
            `${BASE_URL}/api/v1/auth/refresh`,
            { refresh_token: refreshToken }
          );
          localStorage.setItem('access_token', data.access_token);
          localStorage.setItem('refresh_token', data.refresh_token);
          original.headers.Authorization = `Bearer ${data.access_token}`;
          return apiClient(original);
        } catch {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

// ── Auth API ──────────────────────────────────────────────────────────────────
export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<TokenResponse>('/auth/login', data).then((r) => r.data),

  register: (data: RegisterRequest) =>
    apiClient.post<User>('/auth/register', data).then((r) => r.data),

  me: () => apiClient.get<User>('/auth/me').then((r) => r.data),

  refresh: (refreshToken: string) =>
    apiClient
      .post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken })
      .then((r) => r.data),
};

// ── Dataset API ───────────────────────────────────────────────────────────────
export const datasetApi = {
  upload: (file: File, name?: string, onProgress?: (pct: number) => void) => {
    const form = new FormData();
    form.append('file', file);
    if (name) form.append('name', name);
    return apiClient
      .post<UploadResult>('/datasets/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (onProgress && e.total) {
            onProgress(Math.round((e.loaded / e.total) * 100));
          }
        },
      })
      .then((r) => r.data);
  },

  list: (page = 1, pageSize = 20, status?: string) =>
    apiClient
      .get<PaginatedResponse<DatasetListItem>>('/datasets', {
        params: { page, page_size: pageSize, status },
      })
      .then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Dataset>(`/datasets/${id}`).then((r) => r.data),

  getSchema: (id: string) =>
    apiClient.get<DatasetSchema>(`/datasets/${id}/schema`).then((r) => r.data),

  preview: (
    id: string,
    page = 1,
    pageSize = 50,
    sortBy?: string,
    sortOrder?: 'asc' | 'desc',
    filterCol?: string,
    filterVal?: string
  ) =>
    apiClient
      .get<DatasetPreview>(`/datasets/${id}/preview`, {
        params: {
          page,
          page_size: pageSize,
          sort_by: sortBy,
          sort_order: sortOrder,
          filter_col: filterCol,
          filter_val: filterVal,
        },
      })
      .then((r) => r.data),

  getProfiling: (id: string) =>
    apiClient
      .get<DatasetProfiling>(`/datasets/${id}/profiling`)
      .then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/datasets/${id}`).then((r) => r.data),
};

// ── Job API ───────────────────────────────────────────────────────────────────
export const jobApi = {
  get: (id: string) =>
    apiClient.get<Job>(`/jobs/${id}`).then((r) => r.data),

  list: (page = 1, pageSize = 20, status?: string) =>
    apiClient
      .get<PaginatedResponse<Job>>('/jobs', {
        params: { page, page_size: pageSize, status },
      })
      .then((r) => r.data),

  cancel: (id: string) =>
    apiClient.post(`/jobs/${id}/cancel`).then((r) => r.data),
};

// ── Chart API ─────────────────────────────────────────────────────────────────
export const chartApi = {
  histogram: (datasetId: string, column: string, bins = 30) =>
    apiClient
      .get<HistogramData>(`/datasets/${datasetId}/charts/histogram`, {
        params: { column, bins },
      })
      .then((r) => r.data),

  bar: (datasetId: string, column: string, topN = 20) =>
    apiClient
      .get<BarChartData>(`/datasets/${datasetId}/charts/bar`, {
        params: { column, top_n: topN },
      })
      .then((r) => r.data),

  boxplot: (datasetId: string, column: string) =>
    apiClient
      .get<BoxPlotData>(`/datasets/${datasetId}/charts/boxplot`, {
        params: { column },
      })
      .then((r) => r.data),

  correlation: (datasetId: string, maxColumns = 20) =>
    apiClient
      .get<CorrelationData>(`/datasets/${datasetId}/charts/correlation`, {
        params: { max_columns: maxColumns },
      })
      .then((r) => r.data),

  nullDistribution: (datasetId: string) =>
    apiClient
      .get(`/datasets/${datasetId}/charts/nulls`)
      .then((r) => r.data),
};

// ── AI API ────────────────────────────────────────────────────────────────────
export const aiApi = {
  summary: (datasetId: string) =>
    apiClient
      .get<AISummary>(`/datasets/${datasetId}/ai/summary`)
      .then((r) => r.data),

  recommendations: (datasetId: string) =>
    apiClient
      .get<AIRecommendations>(`/datasets/${datasetId}/ai/recommendations`)
      .then((r) => r.data),

  chat: (
    datasetId: string,
    message: string,
    history: ChatMessage[]
  ) =>
    apiClient
      .post<{ message: string; role: string }>(`/datasets/${datasetId}/ai/chat`, {
        message,
        history,
      })
      .then((r) => r.data),
};

export default apiClient;