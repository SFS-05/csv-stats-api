import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  BarChart3,
  Brain,
  CheckCircle,
  Database,
  Lightbulb,
  Loader2,
  MessageSquare,
  Shield,
  Sparkles,
  Star,
  TrendingUp,
  Wrench,
  Zap,
} from 'lucide-react';
import { useDatasets } from '@/hooks/useDatasets';
import { aiApi } from '@/services/api';
import { formatBytes, formatNumber } from '@/utils/format';
import { cn } from '@/utils/cn';

export default function AIInsightsPage() {
  const navigate = useNavigate();
  const { data: datasetsPage, isLoading: datasetsLoading } = useDatasets(1, 100);
  const readyDatasets = (datasetsPage?.items ?? []).filter((d) => d.status === 'ready');
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);

  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
  } = useQuery({
    queryKey: ['ai', 'summary', selectedDatasetId],
    queryFn: () => aiApi.summary(selectedDatasetId!),
    enabled: !!selectedDatasetId,
    staleTime: 300_000,
    retry: 1,
  });

  const {
    data: recommendations,
    isLoading: recsLoading,
    error: recsError,
  } = useQuery({
    queryKey: ['ai', 'recommendations', selectedDatasetId],
    queryFn: () => aiApi.recommendations(selectedDatasetId!),
    enabled: !!selectedDatasetId,
    staleTime: 300_000,
    retry: 1,
  });

  const selectedDataset = readyDatasets.find((d) => d.id === selectedDatasetId);
  const isAnalyzing = summaryLoading || recsLoading;
  const hasError = summaryError || recsError;

  const recIcons: Record<string, React.ReactNode> = {
    missing_values: <AlertTriangle className="w-4 h-4 text-amber-400" />,
    outliers: <TrendingUp className="w-4 h-4 text-orange-400" />,
    encoding: <Wrench className="w-4 h-4 text-blue-400" />,
    scaling: <BarChart3 className="w-4 h-4 text-cyan-400" />,
    feature_engineering: <Sparkles className="w-4 h-4 text-purple-400" />,
    drop_candidates: <Database className="w-4 h-4 text-red-400" />,
    leakage_risks: <Shield className="w-4 h-4 text-rose-400" />,
    imbalance_warnings: <Zap className="w-4 h-4 text-yellow-400" />,
  };

  const recLabels: Record<string, string> = {
    missing_values: 'Missing Values',
    outliers: 'Outlier Handling',
    encoding: 'Feature Encoding',
    scaling: 'Feature Scaling',
    feature_engineering: 'Feature Engineering',
    drop_candidates: 'Drop Candidates',
    leakage_risks: 'Leakage Risks',
    imbalance_warnings: 'Class Imbalance',
  };

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Brain className="w-7 h-7 text-purple-400" />
            AI Insights
          </h1>
          <p className="text-gray-400 mt-1">
            AI-powered dataset analysis grounded in actual computed statistics
          </p>
        </div>
        {selectedDatasetId && (
          <button
            onClick={() => navigate(`/datasets/${selectedDatasetId}/chat`)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-xl transition-colors"
          >
            <MessageSquare className="w-4 h-4" />
            Chat with Dataset
          </button>
        )}
      </div>

      {/* Dataset Selector */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Select Dataset for Analysis
        </h2>

        {datasetsLoading ? (
          <div className="grid grid-cols-3 gap-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-800 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : readyDatasets.length === 0 ? (
          <div className="text-center py-10">
            <Database className="w-10 h-10 text-gray-700 mx-auto mb-3" />
            <p className="text-gray-400">No datasets ready for AI analysis</p>
            <button
              onClick={() => navigate('/datasets')}
              className="mt-3 text-sm text-indigo-400 hover:text-indigo-300"
            >
              Upload a dataset →
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {readyDatasets.map((dataset) => (
              <motion.button
                key={dataset.id}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                onClick={() => setSelectedDatasetId(dataset.id)}
                className={cn(
                  'text-left p-4 rounded-xl border transition-all',
                  selectedDatasetId === dataset.id
                    ? 'bg-purple-900/30 border-purple-700/60 ring-1 ring-purple-600/30'
                    : 'bg-gray-800/50 border-gray-700 hover:border-gray-600'
                )}
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-white truncate">{dataset.name}</h3>
                  {selectedDatasetId === dataset.id && (
                    <CheckCircle className="w-4 h-4 text-purple-400 flex-shrink-0" />
                  )}
                </div>
                <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                  <span>{formatBytes(dataset.file_size_bytes)}</span>
                  <span>{dataset.row_count ? `${formatNumber(dataset.row_count)} rows` : ''}</span>
                  <span>{dataset.column_count ? `${dataset.column_count} cols` : ''}</span>
                </div>
              </motion.button>
            ))}
          </div>
        )}
      </div>

      {/* Loading State */}
      <AnimatePresence>
        {isAnalyzing && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="bg-purple-900/20 border border-purple-800/40 rounded-xl p-8 text-center"
          >
            <Loader2 className="w-8 h-8 text-purple-400 animate-spin mx-auto mb-3" />
            <p className="text-white font-medium">Generating AI Analysis...</p>
            <p className="text-gray-400 text-sm mt-1">
              Analyzing profiling statistics and generating insights
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error State */}
      {hasError && !isAnalyzing && (
        <div className="bg-red-900/20 border border-red-800/40 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
          <p className="text-white font-medium">Analysis Failed</p>
          <p className="text-gray-400 text-sm mt-1">
            AI service may be unavailable. Make sure GEMINI_API_KEY is set.
          </p>
        </div>
      )}

      {/* Summary Section */}
      {summary && !summaryLoading && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          {/* AI Summary */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="p-5 border-b border-gray-800 flex items-center gap-3">
              <div className="w-8 h-8 bg-purple-900/50 rounded-lg flex items-center justify-center">
                <Brain className="w-4 h-4 text-purple-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">AI Dataset Summary</h3>
                <p className="text-xs text-gray-400">
                  {selectedDataset?.name}
                </p>
              </div>
            </div>
            <div className="p-5">
              <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
                {summary.summary}
              </p>
            </div>
          </div>

          {/* ML Readiness Score */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <Star className="w-5 h-5 text-amber-400" />
                <h4 className="text-sm font-semibold text-white">ML Readiness Score</h4>
              </div>
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold text-white">
                  {summary.ml_readiness_score ?? 0}
                </span>
                <span className="text-lg text-gray-400 mb-1">/100</span>
              </div>
              <div className="mt-3 h-2 bg-gray-800 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${summary.ml_readiness_score ?? 0}%` }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                  className={cn(
                    'h-full rounded-full',
                    (summary.ml_readiness_score ?? 0) >= 70
                      ? 'bg-green-500'
                      : (summary.ml_readiness_score ?? 0) >= 40
                      ? 'bg-amber-500'
                      : 'bg-red-500'
                  )}
                />
              </div>
              <p className="text-xs text-gray-400 mt-2">
                {summary.ml_readiness_justification}
              </p>
            </div>

            {/* Quality Assessment */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <Shield className="w-5 h-5 text-cyan-400" />
                <h4 className="text-sm font-semibold text-white">Quality Assessment</h4>
              </div>
              <p className="text-gray-300 text-sm leading-relaxed">
                {summary.quality_assessment}
              </p>
            </div>

            {/* Top Concerns */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <h4 className="text-sm font-semibold text-white">Top Concerns</h4>
              </div>
              <ul className="space-y-2">
                {(summary.top_concerns ?? []).map((concern: string, i: number) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="w-1.5 h-1.5 bg-amber-400 rounded-full mt-1.5 flex-shrink-0" />
                    <span className="text-sm text-gray-300">{concern}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Characteristics */}
          {summary.characteristics && summary.characteristics.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-yellow-400" />
                Key Characteristics
              </h4>
              <div className="flex flex-wrap gap-2">
                {summary.characteristics.map((char: string, i: number) => (
                  <span
                    key={i}
                    className="text-xs px-3 py-1.5 bg-gray-800 text-gray-300 rounded-lg border border-gray-700"
                  >
                    {char}
                  </span>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      )}

      {/* Recommendations Section */}
      {recommendations && !recsLoading && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden"
        >
          <div className="p-5 border-b border-gray-800 flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-900/50 rounded-lg flex items-center justify-center">
              <Wrench className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">
                AI Preprocessing & ML Recommendations
              </h3>
              <p className="text-xs text-gray-400">
                Actionable steps to improve your dataset for machine learning
              </p>
            </div>
          </div>
          <div className="divide-y divide-gray-800">
            {Object.entries(recommendations).map(([key, value]) => (
              <div key={key} className="p-5 hover:bg-gray-800/30 transition-colors">
                <div className="flex items-center gap-3 mb-2">
                  {recIcons[key] ?? <Wrench className="w-4 h-4 text-gray-400" />}
                  <h4 className="text-sm font-semibold text-white">
                    {recLabels[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </h4>
                </div>
                <p className="text-sm text-gray-300 leading-relaxed pl-7 whitespace-pre-wrap">
                  {value as string}
                </p>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Prompt to select */}
      {!selectedDatasetId && !datasetsLoading && readyDatasets.length > 0 && (
        <div className="text-center py-12">
          <Brain className="w-16 h-16 text-gray-700 mx-auto mb-4" />
          <p className="text-gray-400 text-lg">Select a dataset above to generate AI insights</p>
          <p className="text-gray-500 text-sm mt-1">
            Analysis is grounded in actual profiling statistics — no hallucination
          </p>
        </div>
      )}
    </div>
  );
}
