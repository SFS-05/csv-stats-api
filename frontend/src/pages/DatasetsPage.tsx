import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import {
  BarChart3,
  Brain,
  ChevronLeft,
  ChevronRight,
  Database,
  Eye,
  Search,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import {
  useDatasets,
  useUploadDataset,
  useDeleteDataset,
  useJobStatus,
} from '@/hooks/useDatasets';
import { formatBytes, formatDate, formatNumber, getStatusBadgeClass } from '@/utils/format';
import { cn } from '@/utils/cn';

type ViewMode = 'grid' | 'table';
type StatusFilter = 'all' | 'ready' | 'processing' | 'failed' | 'pending';

export default function DatasetsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(12);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const { data: datasetsPage, isLoading } = useDatasets(
    page,
    pageSize,
    statusFilter === 'all' ? undefined : statusFilter
  );
  const uploadMutation = useUploadDataset();
  const deleteMutation = useDeleteDataset();
  const { data: jobStatus } = useJobStatus(activeJobId);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'text/csv': ['.csv'],
      'text/tab-separated-values': ['.tsv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/json': ['.json'],
      'application/octet-stream': ['.parquet'],
    },
    maxSize: 500 * 1024 * 1024,
    multiple: false,
    onDrop: async (accepted) => {
      if (!accepted[0]) return;
      try {
        const result = await uploadMutation.mutateAsync({
          file: accepted[0],
          onProgress: setUploadProgress,
        });
        setActiveJobId(result.job_id);
        toast.success('Dataset uploaded! Processing started.');
        setShowUpload(false);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Upload failed';
        toast.error(msg);
      }
    },
  });

  const filteredItems = (datasetsPage?.items ?? []).filter((d) =>
    search ? d.name.toLowerCase().includes(search.toLowerCase()) : true
  );

  const totalPages = Math.ceil((datasetsPage?.total ?? 0) / pageSize);

  const handleDelete = async (id: string) => {
    try {
      await deleteMutation.mutateAsync(id);
      toast.success('Dataset deleted');
      setDeleteConfirm(null);
    } catch {
      toast.error('Failed to delete dataset');
    }
  };

  const statusFilters: { key: StatusFilter; label: string; color: string }[] = [
    { key: 'all', label: 'All', color: 'text-gray-400' },
    { key: 'ready', label: 'Ready', color: 'text-green-400' },
    { key: 'processing', label: 'Processing', color: 'text-yellow-400' },
    { key: 'failed', label: 'Failed', color: 'text-red-400' },
    { key: 'pending', label: 'Pending', color: 'text-gray-400' },
  ];

  const formatIcons: Record<string, string> = {
    csv: '📊',
    tsv: '📋',
    xlsx: '📗',
    xls: '📗',
    json: '📝',
    jsonl: '📝',
    parquet: '⚡',
  };

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Database className="w-7 h-7 text-indigo-400" />
            Datasets
          </h1>
          <p className="text-gray-400 mt-1">
            Manage, explore, and analyze your uploaded datasets
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => setShowUpload(!showUpload)}
          className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl transition-colors"
        >
          <Upload className="w-4 h-4" />
          Upload Dataset
        </motion.button>
      </div>

      {/* Upload Section */}
      <AnimatePresence>
        {showUpload && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                  <Upload className="w-5 h-5 text-indigo-400" />
                  Upload New Dataset
                </h2>
                <button
                  onClick={() => setShowUpload(false)}
                  className="p-1 hover:bg-gray-800 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-gray-400" />
                </button>
              </div>
              <div
                {...getRootProps()}
                className={cn(
                  'border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all',
                  isDragActive
                    ? 'border-indigo-500 bg-indigo-900/20 scale-[1.01]'
                    : 'border-gray-700 hover:border-gray-600 hover:bg-gray-800/50'
                )}
              >
                <input {...getInputProps()} />
                <Upload className="w-10 h-10 text-gray-500 mx-auto mb-3" />
                <p className="text-gray-300 font-medium">
                  {isDragActive ? 'Drop your file here' : 'Drag & drop or click to upload'}
                </p>
                <p className="text-gray-500 text-sm mt-1">
                  CSV, TSV, XLSX, JSON, JSONL, Parquet — up to 500 MB
                </p>
              </div>

              {uploadMutation.isPending && (
                <div className="mt-4">
                  <div className="flex justify-between text-sm text-gray-400 mb-1">
                    <span>Uploading...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-indigo-600 rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Processing Job Banner */}
      {activeJobId && jobStatus && !['success', 'failure', 'revoked'].includes(jobStatus.status) && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-indigo-900/30 border border-indigo-800/50 rounded-xl p-4"
        >
          <div className="flex items-center justify-between">
            <span className="text-sm text-indigo-300">
              ⚡ Processing: {jobStatus.progress_message ?? 'Working...'}
            </span>
            <span className="text-sm font-medium text-indigo-400">
              {jobStatus.progress_pct}%
            </span>
          </div>
          <div className="h-1.5 bg-indigo-900/50 rounded-full mt-2 overflow-hidden">
            <motion.div
              className="h-full bg-indigo-500 rounded-full"
              animate={{ width: `${jobStatus.progress_pct}%` }}
            />
          </div>
        </motion.div>
      )}

      {/* Filters & Search */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          {statusFilters.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => { setStatusFilter(key); setPage(1); }}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
                statusFilter === key
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search datasets..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500 w-64"
            />
          </div>
          <div className="flex bg-gray-800 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                'p-2 rounded-md transition-colors',
                viewMode === 'grid' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'
              )}
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                <rect x="0" y="0" width="7" height="7" rx="1" />
                <rect x="9" y="0" width="7" height="7" rx="1" />
                <rect x="0" y="9" width="7" height="7" rx="1" />
                <rect x="9" y="9" width="7" height="7" rx="1" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={cn(
                'p-2 rounded-md transition-colors',
                viewMode === 'table' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'
              )}
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                <rect x="0" y="1" width="16" height="2" rx="0.5" />
                <rect x="0" y="5" width="16" height="2" rx="0.5" />
                <rect x="0" y="9" width="16" height="2" rx="0.5" />
                <rect x="0" y="13" width="16" height="2" rx="0.5" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="grid grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-48 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && filteredItems.length === 0 && (
        <div className="text-center py-20">
          <Database className="w-16 h-16 text-gray-700 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-400">No datasets found</h3>
          <p className="text-gray-500 mt-1">
            {search || statusFilter !== 'all'
              ? 'Try adjusting your filters'
              : 'Upload your first dataset to get started'}
          </p>
          {!search && statusFilter === 'all' && (
            <button
              onClick={() => setShowUpload(true)}
              className="mt-4 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl transition-colors"
            >
              Upload Dataset
            </button>
          )}
        </div>
      )}

      {/* Grid View */}
      {!isLoading && filteredItems.length > 0 && viewMode === 'grid' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredItems.map((dataset, i) => (
            <motion.div
              key={dataset.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => navigate(`/datasets/${dataset.id}`)}
              className="group bg-gray-900 border border-gray-800 rounded-xl p-5 cursor-pointer hover:border-gray-700 hover:bg-gray-900/80 transition-all relative"
            >
              {/* Status badge */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{formatIcons[dataset.file_format] ?? '📄'}</span>
                  <span className="text-xs px-2 py-0.5 bg-gray-800 text-gray-400 rounded-md uppercase font-mono">
                    {dataset.file_format}
                  </span>
                </div>
                <span
                  className={cn(
                    'text-xs px-2 py-1 rounded-full border',
                    getStatusBadgeClass(dataset.status)
                  )}
                >
                  {dataset.status}
                </span>
              </div>

              {/* Name */}
              <h3 className="text-sm font-semibold text-white truncate mb-1 group-hover:text-indigo-300 transition-colors">
                {dataset.name}
              </h3>
              <p className="text-xs text-gray-500 truncate mb-4">
                {dataset.original_filename}
              </p>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500">Size</p>
                  <p className="text-xs font-medium text-gray-300 mt-0.5">
                    {formatBytes(dataset.file_size_bytes)}
                  </p>
                </div>
                <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500">Rows</p>
                  <p className="text-xs font-medium text-gray-300 mt-0.5">
                    {dataset.row_count ? formatNumber(dataset.row_count) : '—'}
                  </p>
                </div>
                <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500">Cols</p>
                  <p className="text-xs font-medium text-gray-300 mt-0.5">
                    {dataset.column_count ?? '—'}
                  </p>
                </div>
              </div>

              {/* Footer */}
              <div className="mt-3 pt-3 border-t border-gray-800 flex items-center justify-between">
                <span className="text-xs text-gray-500">
                  {formatDate(dataset.created_at)}
                </span>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate(`/datasets/${dataset.id}`); }}
                    className="p-1.5 hover:bg-gray-700 rounded-lg transition-colors"
                    title="Explore"
                  >
                    <Eye className="w-3.5 h-3.5 text-gray-400" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate(`/visualizations/${dataset.id}`); }}
                    className="p-1.5 hover:bg-gray-700 rounded-lg transition-colors"
                    title="Visualize"
                  >
                    <BarChart3 className="w-3.5 h-3.5 text-gray-400" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate(`/datasets/${dataset.id}/chat`); }}
                    className="p-1.5 hover:bg-gray-700 rounded-lg transition-colors"
                    title="AI Chat"
                  >
                    <Brain className="w-3.5 h-3.5 text-gray-400" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setDeleteConfirm(dataset.id); }}
                    className="p-1.5 hover:bg-red-900/50 rounded-lg transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-red-400" />
                  </button>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Table View */}
      {!isLoading && filteredItems.length > 0 && viewMode === 'table' && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Name</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Format</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Size</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Rows</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Columns</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Created</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {filteredItems.map((dataset) => (
                <tr
                  key={dataset.id}
                  onClick={() => navigate(`/datasets/${dataset.id}`)}
                  className="hover:bg-gray-800/30 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span>{formatIcons[dataset.file_format] ?? '📄'}</span>
                      <div>
                        <p className="font-medium text-white truncate max-w-xs">{dataset.name}</p>
                        <p className="text-xs text-gray-500 truncate max-w-xs">{dataset.original_filename}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2 py-0.5 bg-gray-800 text-gray-400 rounded-md uppercase font-mono">
                      {dataset.file_format}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-300">{formatBytes(dataset.file_size_bytes)}</td>
                  <td className="px-4 py-3 text-right text-gray-300">{dataset.row_count ? formatNumber(dataset.row_count) : '—'}</td>
                  <td className="px-4 py-3 text-right text-gray-300">{dataset.column_count ?? '—'}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={cn('text-xs px-2 py-1 rounded-full border', getStatusBadgeClass(dataset.status))}>
                      {dataset.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{formatDate(dataset.created_at)}</td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/visualizations/${dataset.id}`); }}
                        className="p-1.5 hover:bg-gray-700 rounded-lg transition-colors"
                        title="Visualize"
                      >
                        <BarChart3 className="w-3.5 h-3.5 text-gray-400" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/datasets/${dataset.id}/chat`); }}
                        className="p-1.5 hover:bg-gray-700 rounded-lg transition-colors"
                        title="AI Chat"
                      >
                        <Brain className="w-3.5 h-3.5 text-gray-400" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); setDeleteConfirm(dataset.id); }}
                        className="p-1.5 hover:bg-red-900/50 rounded-lg transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-red-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {!isLoading && totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400">
            Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, datasetsPage?.total ?? 0)} of{' '}
            {formatNumber(datasetsPage?.total ?? 0)} datasets
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 text-gray-400 hover:text-white rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm"
            >
              <ChevronLeft className="w-4 h-4" /> Prev
            </button>
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                let pageNum: number;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (page <= 3) {
                  pageNum = i + 1;
                } else if (page >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = page - 2 + i;
                }
                return (
                  <button
                    key={pageNum}
                    onClick={() => setPage(pageNum)}
                    className={cn(
                      'w-8 h-8 rounded-lg text-sm font-medium transition-colors',
                      page === pageNum
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:text-white'
                    )}
                  >
                    {pageNum}
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 text-gray-400 hover:text-white rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
            onClick={() => setDeleteConfirm(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-sm w-full mx-4"
            >
              <div className="w-12 h-12 bg-red-900/30 rounded-xl flex items-center justify-center mx-auto mb-4">
                <Trash2 className="w-6 h-6 text-red-400" />
              </div>
              <h3 className="text-lg font-semibold text-white text-center">Delete Dataset?</h3>
              <p className="text-sm text-gray-400 text-center mt-2">
                This action cannot be undone. The dataset and all its profiling data will be permanently removed.
              </p>
              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="flex-1 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium rounded-xl transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleDelete(deleteConfirm)}
                  disabled={deleteMutation.isPending}
                  className="flex-1 px-4 py-2.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white font-medium rounded-xl transition-colors"
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
