import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  BarChart3,
  Eye,
  Layers,
  LineChart,
  PieChart,
  TrendingUp,
} from 'lucide-react';
import { useDatasets } from '@/hooks/useDatasets';
import { formatBytes, formatNumber } from '@/utils/format';
import { cn } from '@/utils/cn';

export default function VisualizationsPage() {
  const navigate = useNavigate();
  const { data: datasetsPage, isLoading } = useDatasets(1, 100);
  const readyDatasets = (datasetsPage?.items ?? []).filter((d) => d.status === 'ready');

  const chartTypes = [
    {
      key: 'correlation',
      label: 'Correlation Heatmap',
      icon: LineChart,
      description: 'Pearson correlation matrix between numeric columns',
      color: 'from-blue-600/20 to-cyan-600/20',
      borderColor: 'border-blue-800/50',
      iconColor: 'text-blue-400',
    },
    {
      key: 'histogram',
      label: 'Histogram',
      icon: BarChart3,
      description: 'Distribution of values in numeric columns',
      color: 'from-indigo-600/20 to-purple-600/20',
      borderColor: 'border-indigo-800/50',
      iconColor: 'text-indigo-400',
    },
    {
      key: 'boxplot',
      label: 'Box Plot',
      icon: TrendingUp,
      description: 'Statistical distribution with outlier detection',
      color: 'from-violet-600/20 to-pink-600/20',
      borderColor: 'border-violet-800/50',
      iconColor: 'text-violet-400',
    },
    {
      key: 'nulls',
      label: 'Null Distribution',
      icon: PieChart,
      description: 'Missing value heatmap across all columns',
      color: 'from-amber-600/20 to-orange-600/20',
      borderColor: 'border-amber-800/50',
      iconColor: 'text-amber-400',
    },
    {
      key: 'bar',
      label: 'Value Counts',
      icon: Layers,
      description: 'Top value distribution in categorical columns',
      color: 'from-emerald-600/20 to-teal-600/20',
      borderColor: 'border-emerald-800/50',
      iconColor: 'text-emerald-400',
    },
  ];

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <BarChart3 className="w-7 h-7 text-indigo-400" />
          Visualization Studio
        </h1>
        <p className="text-gray-400 mt-1">
          Explore your data through interactive charts and visualizations
        </p>
      </div>

      {/* Chart Type Gallery */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Available Chart Types
        </h2>
        <div className="grid grid-cols-5 gap-3">
          {chartTypes.map(({ key, label, icon: Icon, description, color, borderColor, iconColor }) => (
            <motion.div
              key={key}
              whileHover={{ y: -2 }}
              className={cn(
                'bg-gradient-to-br rounded-xl p-4 border cursor-default',
                color,
                borderColor
              )}
            >
              <Icon className={cn('w-8 h-8 mb-3', iconColor)} />
              <h3 className="text-sm font-semibold text-white mb-1">{label}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">{description}</p>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Dataset Selection */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Select a Dataset to Visualize
        </h2>

        {isLoading ? (
          <div className="grid grid-cols-2 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-32 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : readyDatasets.length === 0 ? (
          <div className="text-center py-16 bg-gray-900 border border-gray-800 rounded-xl">
            <BarChart3 className="w-12 h-12 text-gray-700 mx-auto mb-3" />
            <p className="text-gray-400 font-medium">No datasets ready for visualization</p>
            <p className="text-gray-500 text-sm mt-1">
              Upload and process a dataset first
            </p>
            <button
              onClick={() => navigate('/datasets')}
              className="mt-4 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-xl transition-colors"
            >
              Go to Datasets
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {readyDatasets.map((dataset, i) => (
              <motion.div
                key={dataset.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                onClick={() => navigate(`/visualizations/${dataset.id}`)}
                className="group bg-gray-900 border border-gray-800 rounded-xl p-5 cursor-pointer hover:border-indigo-700/50 hover:bg-gray-900/80 transition-all"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-semibold text-white truncate group-hover:text-indigo-300 transition-colors">
                      {dataset.name}
                    </h3>
                    <p className="text-xs text-gray-500 mt-1 truncate">
                      {dataset.original_filename}
                    </p>
                  </div>
                  <div className="ml-4 p-2 bg-indigo-900/30 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity">
                    <Eye className="w-4 h-4 text-indigo-400" />
                  </div>
                </div>

                <div className="flex items-center gap-4 mt-4">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 bg-green-400 rounded-full" />
                    <span className="text-xs text-gray-400">Ready</span>
                  </div>
                  <span className="text-xs text-gray-500">
                    {formatBytes(dataset.file_size_bytes)}
                  </span>
                  <span className="text-xs text-gray-500">
                    {dataset.row_count ? `${formatNumber(dataset.row_count)} rows` : ''}
                  </span>
                  <span className="text-xs text-gray-500">
                    {dataset.column_count ? `${dataset.column_count} cols` : ''}
                  </span>
                </div>

                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-800">
                  {['Correlation', 'Histogram', 'BoxPlot', 'Nulls', 'Bars'].map((type) => (
                    <span
                      key={type}
                      className="text-[10px] px-2 py-0.5 bg-gray-800 text-gray-400 rounded-md"
                    >
                      {type}
                    </span>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
