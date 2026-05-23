import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import {
  BarChart3,
  Brain,
  Database,
  TrendingUp,
  Upload,
  Zap,
} from 'lucide-react';
import { useDatasets, useUploadDataset, useJobStatus } from '@/hooks/useDatasets';
import { formatBytes, formatDate, getStatusBadgeClass } from '@/utils/format';
import { cn } from '@/utils/cn';

export default function Dashboard() {
  const navigate = useNavigate();
  const [uploadProgress, setUploadProgress] = useState(0);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const { data: datasetsPage, isLoading } = useDatasets(1, 5);
  const uploadMutation = useUploadDataset();
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
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Upload failed';
        toast.error(msg);
      }
    },
  });

  const stats = [
    {
      label: 'Total Datasets',
      value: datasetsPage?.total ?? 0,
      icon: Database,
      color: 'text-indigo-400',
      bg: 'bg-indigo-900/30',
    },
    {
      label: 'Ready',
      value: datasetsPage?.items.filter((d) => d.status === 'ready').length ?? 0,
      icon: TrendingUp,
      color: 'text-green-400',
      bg: 'bg-green-900/30',
    },
    {
      label: 'Processing',
      value: datasetsPage?.items.filter((d) => d.status === 'processing').length ?? 0,
      icon: Zap,
      color: 'text-yellow-400',
      bg: 'bg-yellow-900/30',
    },
    {
      label: 'AI Analyzed',
      value: 0,
      icon: Brain,
      color: 'text-purple-400',
      bg: 'bg-purple-900/30',
    },
  ];

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-400 mt-1">Upload datasets and get AI-powered insights</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {stats.map(({ label, value, icon: Icon, color, bg }) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gray-900 border border-gray-800 rounded-xl p-5"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">{label}</p>
                <p className="text-2xl font-bold text-white mt-1">{value}</p>
              </div>
              <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', bg)}>
                <Icon className={cn('w-5 h-5', color)} />
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Upload zone */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Upload className="w-5 h-5 text-indigo-400" />
          Upload Dataset
        </h2>
        <div
          {...getRootProps()}
          className={cn(
            'border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors',
            isDragActive
              ? 'border-indigo-500 bg-indigo-900/20'
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

        {activeJobId && jobStatus && (
          <div className="mt-4 p-4 bg-gray-800 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-300">
                Processing: {jobStatus.progress_message ?? 'Working...'}
              </span>
              <span className="text-sm font-medium text-indigo-400">
                {jobStatus.progress_pct}%
              </span>
            </div>
            <div className="h-1.5 bg-gray-700 rounded-full mt-2 overflow-hidden">
              <motion.div
                className="h-full bg-indigo-500 rounded-full"
                animate={{ width: `${jobStatus.progress_pct}%` }}
              />
            </div>
            {jobStatus.status === 'success' && (
              <p className="text-green-400 text-sm mt-2">
                ✓ Profiling complete!{' '}
                <button
                  className="underline"
                  onClick={() => navigate('/datasets')}
                >
                  View dataset
                </button>
              </p>
            )}
          </div>
        )}
      </div>

      {/* Recent datasets */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-400" />
            Recent Datasets
          </h2>
          <button
            onClick={() => navigate('/datasets')}
            className="text-sm text-indigo-400 hover:text-indigo-300"
          >
            View all →
          </button>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-14 bg-gray-800 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : datasetsPage?.items.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            No datasets yet. Upload one above to get started.
          </p>
        ) : (
          <div className="space-y-2">
            {datasetsPage?.items.map((dataset) => (
              <motion.div
                key={dataset.id}
                whileHover={{ x: 2 }}
                onClick={() => navigate(`/datasets/${dataset.id}`)}
                className="flex items-center justify-between p-3 bg-gray-800 rounded-lg cursor-pointer hover:bg-gray-750 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <BarChart3 className="w-4 h-4 text-indigo-400" />
                  <div>
                    <p className="text-sm font-medium text-white">{dataset.name}</p>
                    <p className="text-xs text-gray-400">
                      {formatBytes(dataset.file_size_bytes)} · {formatDate(dataset.created_at)}
                    </p>
                  </div>
                </div>
                <span
                  className={cn(
                    'text-xs px-2 py-1 rounded-full border',
                    getStatusBadgeClass(dataset.status)
                  )}
                >
                  {dataset.status}
                </span>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}