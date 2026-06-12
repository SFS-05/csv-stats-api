import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Loader2,
  RefreshCw,
  XCircle,
  Zap,
} from 'lucide-react';
import { useJobs, useCancelJob } from '@/hooks/useDatasets';
import { formatDate, formatDuration, getStatusBadgeClass } from '@/utils/format';
import { cn } from '@/utils/cn';
import toast from 'react-hot-toast';

type StatusFilter = 'all' | 'queued' | 'started' | 'success' | 'failure' | 'revoked';

export default function JobsPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const { data: jobsPage, isLoading, refetch } = useJobs(
    page,
    pageSize,
    statusFilter === 'all' ? undefined : statusFilter
  );

  const cancelMutation = useCancelJob();

  const handleCancel = async (jobId: string) => {
    try {
      await cancelMutation.mutateAsync(jobId);
      toast.success('Job cancellation request sent');
      refetch();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to cancel job');
    }
  };

  const totalPages = Math.ceil((jobsPage?.total ?? 0) / pageSize);

  const statusFilters: { key: StatusFilter; label: string }[] = [
    { key: 'all', label: 'All Jobs' },
    { key: 'queued', label: 'Queued' },
    { key: 'started', label: 'Started' },
    { key: 'success', label: 'Success' },
    { key: 'failure', label: 'Failure' },
    { key: 'revoked', label: 'Cancelled' },
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="w-5 h-5 text-green-400" />;
      case 'failure':
        return <XCircle className="w-5 h-5 text-red-400" />;
      case 'queued':
        return <Clock className="w-5 h-5 text-blue-400" />;
      case 'started':
      case 'progress':
        return <Loader2 className="w-5 h-5 text-yellow-400 animate-spin" />;
      case 'revoked':
        return <AlertTriangle className="w-5 h-5 text-gray-400" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Zap className="w-7 h-7 text-yellow-400" />
            Background Jobs
          </h1>
          <p className="text-gray-400 mt-1">
            Monitor async profiling tasks, schema extraction and AI generation jobs.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-4 py-2 bg-gray-850 hover:bg-gray-800 border border-gray-700 hover:border-gray-650 rounded-xl text-sm font-medium text-gray-300 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between gap-4 border-b border-gray-800 pb-4">
        <div className="flex items-center gap-2 overflow-x-auto">
          {statusFilters.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => { setStatusFilter(key); setPage(1); }}
              className={cn(
                'px-4 py-2 text-xs font-semibold rounded-xl border transition-all whitespace-nowrap',
                statusFilter === key
                  ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                  : 'bg-gray-900 border-gray-800 text-gray-400 hover:text-white hover:border-gray-700'
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="text-xs text-gray-500 font-medium">
          Auto-refreshing every 5s
        </span>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && (jobsPage?.items ?? []).length === 0 && (
        <div className="text-center py-20 bg-gray-900 border border-gray-800 rounded-2xl">
          <Zap className="w-12 h-12 text-gray-700 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-gray-400">No jobs found</h3>
          <p className="text-sm text-gray-500 mt-1">
            {statusFilter === 'all'
              ? "You haven't run any background jobs yet."
              : `No jobs found with status "${statusFilter}"`}
          </p>
        </div>
      )}

      {/* Jobs list */}
      {!isLoading && (jobsPage?.items ?? []).length > 0 && (
        <div className="space-y-3">
          {jobsPage?.items.map((job) => {
            const isCancellable = ['queued', 'started', 'progress'].includes(job.status);
            return (
              <motion.div
                key={job.job_id}
                layout
                className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-gray-700 transition-colors"
              >
                <div className="flex items-start gap-4">
                  <div className="mt-1 flex-shrink-0">
                    {getStatusIcon(job.status)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-semibold text-white font-mono">
                        Job: {job.job_id.slice(0, 8)}...
                      </h4>
                      <span className={cn('text-[10px] px-2 py-0.5 rounded-full border uppercase', getStatusBadgeClass(job.status))}>
                        {job.status}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-gray-400">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-gray-500" />
                        Queued: {formatDate(job.created_at)}
                      </span>
                      {job.duration_seconds && (
                        <span>Duration: {formatDuration(job.duration_seconds)}</span>
                      )}
                    </div>

                    {/* Progress details */}
                    {(job.status === 'started' || job.status === 'progress' || job.progress_pct > 0) && (
                      <div className="mt-3 w-64 md:w-80">
                        <div className="flex justify-between text-[10px] text-gray-400 mb-1">
                          <span className="truncate max-w-[200px]">{job.progress_message ?? 'Processing...'}</span>
                          <span>{job.progress_pct}%</span>
                        </div>
                        <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                          <motion.div
                            className="h-full bg-yellow-500 rounded-full"
                            animate={{ width: `${job.progress_pct}%` }}
                            transition={{ duration: 0.3 }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Error message */}
                    {job.error_message && (
                      <p className="mt-2 text-xs text-red-400 bg-red-900/10 border border-red-800/30 rounded-lg p-2 max-w-xl">
                        Error: {job.error_message}
                      </p>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-end gap-2">
                  {isCancellable && (
                    <button
                      onClick={() => handleCancel(job.job_id)}
                      disabled={cancelMutation.isPending}
                      className="px-3.5 py-1.5 bg-red-950/40 hover:bg-red-900/40 border border-red-900/30 hover:border-red-800/50 rounded-lg text-xs font-semibold text-red-400 transition-colors"
                    >
                      Cancel Job
                    </button>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {!isLoading && totalPages > 1 && (
        <div className="flex items-center justify-between pt-4">
          <span className="text-sm text-gray-400">
            Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, jobsPage?.total ?? 0)} of{' '}
            {jobsPage?.total ?? 0} jobs
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 text-gray-400 hover:text-white rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm"
            >
              <ChevronLeft className="w-4 h-4" /> Prev
            </button>
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
    </div>
  );
}
