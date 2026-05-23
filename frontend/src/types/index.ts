/**
 * Shared TypeScript types matching backend Pydantic schemas.
 */

// ── Auth ──────────────────────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  role: 'admin' | 'analyst' | 'viewer';
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
  full_name?: string;
}

// ── Datasets ──────────────────────────────────────────────────────────────────
export type DatasetStatus =
  | 'pending'
  | 'uploading'
  | 'uploaded'
  | 'processing'
  | 'ready'
  | 'failed'
  | 'deleted';

export type FileFormat = 'csv' | 'tsv' | 'xlsx' | 'xls' | 'json' | 'jsonl' | 'parquet';

export interface DatasetListItem {
  id: string;
  name: string;
  original_filename: string;
  file_format: FileFormat;
  file_size_bytes: number;
  row_count: number | null;
  column_count: number | null;
  status: DatasetStatus;
  created_at: string;
}

export interface Dataset extends DatasetListItem {
  mime_type: string;
  memory_usage_bytes: number | null;
  error_message: string | null;
  updated_at: string;
  processing_started_at: string | null;
  processing_completed_at: string | null;
}

export interface ColumnSchema {
  name: string;
  dtype: string;
  inferred_type: 'numeric' | 'categorical' | 'datetime' | 'text' | 'boolean';
  nullable: boolean;
  null_count: number;
  null_pct: number;
  unique_count: number | null;
  sample_values: unknown[];
}

export interface DatasetSchema {
  dataset_id: string;
  columns: ColumnSchema[];
  row_count: number;
  column_count: number;
  memory_usage_bytes: number;
  inferred_at: string;
}

export interface PreviewRow {
  [key: string]: unknown;
}

export interface DatasetPreview {
  dataset_id: string;
  columns: string[];
  rows: PreviewRow[];
  total_rows: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// ── Profiling ─────────────────────────────────────────────────────────────────
export interface NumericStats {
  mean: number | null;
  median: number | null;
  std: number | null;
  variance: number | null;
  min: number | null;
  max: number | null;
  p25: number | null;
  p75: number | null;
  p95: number | null;
  p99: number | null;
  skewness: number | null;
  kurtosis: number | null;
  outlier_count: number;
  outlier_pct: number;
}

export interface CategoricalStats {
  cardinality: number;
  entropy: number | null;
  top_values: Array<{ value: string; count: number; pct: number }>;
  rare_category_count: number;
  rare_category_pct: number;
}

export interface ColumnProfile {
  column_name: string;
  inferred_type: string;
  null_count: number;
  null_pct: number;
  unique_count: number;
  unique_pct: number;
  numeric_stats?: NumericStats;
  categorical_stats?: CategoricalStats;
  datetime_stats?: {
    min_date: string | null;
    max_date: string | null;
    range_days: number | null;
    null_count: number;
    gap_count: number | null;
  };
  text_stats?: {
    avg_length: number | null;
    min_length: number | null;
    max_length: number | null;
    empty_count: number;
    language_hint: string | null;
  };
}

export interface DatasetProfiling {
  dataset_id: string;
  row_count: number;
  column_count: number;
  memory_usage_bytes: number;
  duplicate_row_count: number;
  duplicate_row_pct: number;
  total_missing_values: number;
  total_missing_pct: number;
  column_profiles: ColumnProfile[];
  profiled_at: string;
}

// ── Jobs ──────────────────────────────────────────────────────────────────────
export type JobStatus =
  | 'queued'
  | 'started'
  | 'progress'
  | 'success'
  | 'failure'
  | 'revoked'
  | 'retry';

export interface Job {
  job_id: string;
  status: JobStatus;
  progress_pct: number;
  progress_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
}

// ── Charts ────────────────────────────────────────────────────────────────────
export interface HistogramBin {
  bin_start: number;
  bin_end: number;
  count: number;
  pct: number;
}

export interface HistogramData {
  column: string;
  type: 'histogram';
  bins: HistogramBin[];
  total_values: number;
  null_count: number;
}

export interface BarChartData {
  column: string;
  type: 'bar';
  bars: Array<{ value: string; count: number; pct: number }>;
  total_values: number;
  null_count: number;
  cardinality: number;
}

export interface BoxPlotData {
  column: string;
  type: 'boxplot';
  data: {
    min: number;
    q1: number;
    median: number;
    q3: number;
    max: number;
    lower_fence: number;
    upper_fence: number;
    outlier_count: number;
    outliers: number[];
  } | null;
}

export interface CorrelationData {
  type: 'correlation';
  columns: string[];
  matrix: (number | null)[][];
}

// ── AI ────────────────────────────────────────────────────────────────────────
export interface AISummary {
  summary: string;
  characteristics: string[];
  quality_assessment: string;
  ml_readiness_score: number;
  ml_readiness_justification: string;
  top_concerns: string[];
}

export interface AIRecommendations {
  missing_values: string;
  outliers: string;
  encoding: string;
  scaling: string;
  feature_engineering: string;
  drop_candidates: string;
  leakage_risks: string;
  imbalance_warnings: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

// ── Pagination ────────────────────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

// ── Upload ────────────────────────────────────────────────────────────────────
export interface UploadResult {
  dataset_id: string;
  job_id: string;
  celery_task_id: string;
  status: string;
  file_format: string;
  file_size_bytes: number;
  checksum_sha256: string;
}