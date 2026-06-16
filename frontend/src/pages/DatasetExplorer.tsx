import { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table';
import { ChevronLeft, ChevronRight, Search, SortAsc, SortDesc } from 'lucide-react';
import { useDataset, useDatasetPreview, useDatasetProfiling } from '@/hooks/useDatasets';
import { formatBytes, formatNumber, formatPct, getStatusBadgeClass } from '@/utils/format';
import { cn } from '@/utils/cn';
import type { PreviewRow } from '@/types';

export default function DatasetExplorer() {
  const { id } = useParams<{ id: string }>();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [sortBy, setSortBy] = useState<string | undefined>();
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [filterCol, setFilterCol] = useState<string | undefined>();
  const [filterVal, setFilterVal] = useState('');
  const [activeTab, setActiveTab] = useState<'preview' | 'profiling' | 'schema'>('preview');

  const { data: dataset } = useDataset(id!);
  const { data: preview, isLoading: previewLoading } = useDatasetPreview(
    id!, page, pageSize, sortBy, sortOrder, filterCol, filterVal || undefined
  );
  const { data: profiling } = useDatasetProfiling(id!, dataset?.status === 'ready');

  const columns: ColumnDef<PreviewRow>[] = (preview?.columns ?? []).map((col) => ({
    id: col,
    accessorKey: col,
    header: () => (
      <button
        className="flex items-center gap-1 text-left font-medium text-gray-300 hover:text-white"
        onClick={() => {
          if (sortBy === col) {
            setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
          } else {
            setSortBy(col);
            setSortOrder('asc');
          }
        }}
      >
        {col}
        {sortBy === col ? (
          sortOrder === 'asc' ? <SortAsc className="w-3 h-3" /> : <SortDesc className="w-3 h-3" />
        ) : null}
      </button>
    ),
    cell: ({ getValue }) => {
      const val = getValue();
      if (val === null || val === undefined) {
        return <span className="text-gray-600 italic">null</span>;
      }
      return <span className="text-gray-200">{String(val)}</span>;
    },
  }));

  const table = useReactTable({
    data: preview?.rows ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: Math.ceil((preview?.total_rows ?? 0) / pageSize),
  });

  if (!dataset) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{dataset.name}</h1>
          <p className="text-gray-400 mt-1">
            {dataset.row_count ? formatNumber(dataset.row_count) : '—'} rows ·{' '}
            {dataset.column_count ?? '—'} columns ·{' '}
            {formatBytes(dataset.file_size_bytes)}
          </p>
        </div>
        <span className={cn('text-xs px-3 py-1.5 rounded-full border', getStatusBadgeClass(dataset.status))}>
          {dataset.status}
        </span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-xl p-1 w-fit">
        {(['preview', 'profiling', 'schema'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-4 py-2 text-sm font-medium rounded-lg transition-colors capitalize',
              activeTab === tab
                ? 'bg-indigo-600 text-white'
                : 'text-gray-400 hover:text-white'
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Preview Tab */}
      {activeTab === 'preview' && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          {/* Filter bar */}
          <div className="p-4 border-b border-gray-800 flex items-center gap-3">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="text"
                placeholder="Filter value..."
                value={filterVal}
                onChange={(e) => { setFilterVal(e.target.value); setPage(1); }}
                className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            {filterVal && (
              <select
                value={filterCol ?? ''}
                onChange={(e) => setFilterCol(e.target.value || undefined)}
                className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="">All columns</option>
                {preview?.columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            )}
            <span className="text-sm text-gray-400 ml-auto">
              {preview ? formatNumber(preview.total_rows) : '—'} total rows
            </span>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            {previewLoading ? (
              <div className="p-8 flex justify-center">
                <div className="animate-spin w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full" />
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  {table.getHeaderGroups().map((hg) => (
                    <tr key={hg.id} className="border-b border-gray-800">
                      {hg.headers.map((header) => (
                        <th
                          key={header.id}
                          className="px-4 py-3 text-left bg-gray-800/50 whitespace-nowrap"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody>
                  {table.getRowModel().rows.map((row, i) => (
                    <tr
                      key={row.id}
                      className={cn(
                        'border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors',
                        i % 2 === 0 ? '' : 'bg-gray-900/30'
                      )}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-4 py-2.5 whitespace-nowrap max-w-xs truncate">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination */}
          <div className="p-4 border-t border-gray-800 flex items-center justify-between">
            <span className="text-sm text-gray-400">
              Page {page} of {Math.ceil((preview?.total_rows ?? 0) / pageSize)}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 rounded-lg bg-gray-800 text-gray-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!preview?.has_more}
                className="p-2 rounded-lg bg-gray-800 text-gray-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Profiling Tab */}
      {activeTab === 'profiling' && profiling && (
        <div className="space-y-4">
          {/* Summary cards */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'Rows', value: formatNumber(profiling.row_count) },
              { label: 'Columns', value: profiling.column_count },
              { label: 'Missing', value: formatPct(profiling.total_missing_pct) },
              { label: 'Duplicates', value: formatPct(profiling.duplicate_row_pct) },
            ].map(({ label, value }) => (
              <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <p className="text-xs text-gray-400">{label}</p>
                <p className="text-xl font-bold text-white mt-1">{value}</p>
              </div>
            ))}
          </div>

          {/* Column profiles */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-gray-800">
              <h3 className="font-semibold text-white">Column Profiles</h3>
            </div>
            <div className="divide-y divide-gray-800">
              {profiling.column_profiles.map((col) => (
                <div key={col.column_name} className="p-4 hover:bg-gray-800/30">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white">{col.column_name}</span>
                      <span className="text-xs px-2 py-0.5 bg-indigo-900/50 text-indigo-400 rounded-full border border-indigo-800">
                        {col.inferred_type}
                      </span>
                    </div>
                    <span className="text-sm text-gray-400">
                      {formatPct(col.null_pct)} null
                    </span>
                  </div>
                  {col.numeric_stats && (
                    <div className="grid grid-cols-6 gap-2 text-xs text-gray-400">
                      <div><span className="text-gray-500">mean</span> {col.numeric_stats.mean?.toFixed(3)}</div>
                      <div><span className="text-gray-500">std</span> {col.numeric_stats.std?.toFixed(3)}</div>
                      <div><span className="text-gray-500">min</span> {col.numeric_stats.min}</div>
                      <div><span className="text-gray-500">max</span> {col.numeric_stats.max}</div>
                      <div><span className="text-gray-500">p25</span> {col.numeric_stats.p25}</div>
                      <div><span className="text-gray-500">p75</span> {col.numeric_stats.p75}</div>
                    </div>
                  )}
                  {col.categorical_stats && (
                    <div className="flex gap-4 text-xs text-gray-400">
                      <span><span className="text-gray-500">cardinality</span> {col.categorical_stats.cardinality}</span>
                      <span><span className="text-gray-500">entropy</span> {col.categorical_stats.entropy?.toFixed(3)}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}