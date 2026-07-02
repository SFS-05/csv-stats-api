import React, { useState, useEffect, useMemo, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import * as echarts from 'echarts'
import { chartApi, datasetApi } from '../services/api'
import { Card, CardHeader, Badge, Button } from '../components/ui'
import { formatNumber } from '../utils/format'

type ChartType = 'histogram' | 'boxplot' | 'correlation' | 'nulls' | 'bar'

// ── ChartPanel wrapper ─────────────────────────────────────────────────────
interface ChartPanelProps {
  title: string
  subtitle?: string
  children: React.ReactNode
  loading?: boolean
  error?: string | null
}

const ChartPanel: React.FC<ChartPanelProps> = ({ title, subtitle, children, loading, error }) => (
  <Card className="h-full">
    <CardHeader title={title} subtitle={subtitle} />
    {loading && (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      </div>
    )}
    {error && (
      <div className="flex items-center justify-center h-64 text-red-500 text-sm">{error}</div>
    )}
    {!loading && !error && children}
  </Card>
)

// ── Generic ECharts wrapper ────────────────────────────────────────────────
interface EChartProps {
  option: echarts.EChartsOption
  height?: number
  className?: string
}

const EChart: React.FC<EChartProps> = ({ option, height = 320, className }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    if (!chartRef.current) {
      chartRef.current = echarts.init(containerRef.current, null, { renderer: 'canvas' })
    }
    chartRef.current.setOption(option, true)
  }, [option])

  useEffect(() => {
    const observer = new ResizeObserver(() => chartRef.current?.resize())
    if (containerRef.current) observer.observe(containerRef.current)
    return () => {
      observer.disconnect()
      chartRef.current?.dispose()
      chartRef.current = null
    }
  }, [])

  return <div ref={containerRef} style={{ height }} className={className} />
}

// ── Histogram ──────────────────────────────────────────────────────────────
const HistogramChart: React.FC<{ datasetId: string; column: string }> = ({ datasetId, column }) => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['viz', 'histogram', datasetId, column],
    queryFn: () => chartApi.histogram(datasetId, column, 30),
    enabled: !!column,
  })

  const bins = data?.bins ?? []
  const binLabels = bins.map(bin => `${bin.bin_start.toFixed(1)} - ${bin.bin_end.toFixed(1)}`)
  const binCounts = bins.map(bin => bin.count)

  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 48, right: 16, top: 16, bottom: 40 },
    xAxis: {
      type: 'category',
      data: binLabels,
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: { type: 'value', name: 'Count', nameTextStyle: { fontSize: 11 } },
    series: [{ type: 'bar', data: binCounts, itemStyle: { color: '#6366f1' }, barMaxWidth: 40 }],
  }

  return (
    <ChartPanel title="Histogram" subtitle={column} loading={isLoading} error={error ? String(error) : null}>
      <EChart option={option} />
    </ChartPanel>
  )
}

// ── Boxplot ────────────────────────────────────────────────────────────────
const BoxplotChart: React.FC<{ datasetId: string; columns: string[] }> = ({ datasetId, columns }) => {
  const results = columns.slice(0, 12).map(col =>
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useQuery({
      queryKey: ['viz', 'boxplot', datasetId, col],
      queryFn: () => chartApi.boxplot(datasetId, col),
      enabled: columns.length > 0,
    })
  )

  const isLoading = results.some(r => r.isLoading)
  const boxData = results
    .filter(r => r.data && r.data.data)
    .map(r => r.data!)
    .map(d => [d.data!.min, d.data!.q1, d.data!.median, d.data!.q3, d.data!.max])

  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'item' },
    grid: { left: 56, right: 16, top: 16, bottom: 48 },
    xAxis: { type: 'category', data: columns.slice(0, boxData.length) },
    yAxis: { type: 'value' },
    series: [{ type: 'boxplot', data: boxData, itemStyle: { color: '#a5b4fc', borderColor: '#6366f1' } }],
  }

  return (
    <ChartPanel title="Boxplot" subtitle="Numeric columns (up to 12)" loading={isLoading}>
      <EChart option={option} />
    </ChartPanel>
  )
}

// ── Correlation Heatmap ────────────────────────────────────────────────────
const CorrelationHeatmap: React.FC<{ datasetId: string }> = ({ datasetId }) => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['viz', 'correlation', datasetId],
    queryFn: () => chartApi.correlation(datasetId, 20),
  })

  const columns: string[] = data?.columns ?? []
  const matrix: (number | null)[][] = data?.matrix ?? []

  const heatmapData: [number, number, number][] = []
  matrix.forEach((row, i) =>
    row.forEach((val, j) => {
      if (val !== null && val !== undefined) {
        heatmapData.push([j, i, parseFloat(val.toFixed(3))])
      }
    })
  )

  const option: echarts.EChartsOption = {
    tooltip: {
      formatter: (p: any) => `${columns[p.data[1]]} × ${columns[p.data[0]]}<br/>r = ${p.data[2]}`,
    },
    grid: { left: 80, right: 80, top: 16, bottom: 80 },
    xAxis: { type: 'category', data: columns, axisLabel: { rotate: 45, fontSize: 11 } },
    yAxis: { type: 'category', data: columns, axisLabel: { fontSize: 11 } },
    visualMap: {
      min: -1, max: 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#3b82f6', '#f9fafb', '#ef4444'] },
    },
    series: [{
      type: 'heatmap',
      data: heatmapData,
      label: { show: columns.length <= 10, fontSize: 10 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
    }],
  }

  return (
    <ChartPanel title="Correlation Heatmap" subtitle="Pearson r between numeric columns" loading={isLoading} error={error ? String(error) : null}>
      <EChart option={option} height={Math.max(320, columns.length * 32 + 120)} />
    </ChartPanel>
  )
}

// ── Null Distribution ──────────────────────────────────────────────────────
const NullsChart: React.FC<{ datasetId: string }> = ({ datasetId }) => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['viz', 'nulls', datasetId],
    queryFn: () => chartApi.nullDistribution(datasetId),
  })

  const columns: string[] = (data as any)?.columns ?? []
  const nullPcts: number[] = (data as any)?.null_percentages ?? []

  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis', formatter: (p: any) => `${(p as any)[0].name}: ${(p as any)[0].value}% null` },
    grid: { left: 120, right: 48, top: 16, bottom: 16 },
    xAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    yAxis: { type: 'category', data: columns, axisLabel: { fontSize: 11 } },
    series: [{
      type: 'bar',
      data: nullPcts,
      itemStyle: { color: (p: any) => (p.value > 50 ? '#ef4444' : p.value > 20 ? '#f59e0b' : '#10b981') },
      label: { show: true, position: 'right', formatter: '{c}%', fontSize: 11 },
    }],
  }

  return (
    <ChartPanel title="Null Distribution" subtitle="% missing per column" loading={isLoading} error={error ? String(error) : null}>
      <EChart option={option} height={Math.max(240, columns.length * 28 + 40)} />
    </ChartPanel>
  )
}

// ── Bar Chart (categorical) ────────────────────────────────────────────────
const BarChart: React.FC<{ datasetId: string; column: string }> = ({ datasetId, column }) => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['viz', 'bar', datasetId, column],
    queryFn: () => chartApi.bar(datasetId, column, 20),
    enabled: !!column,
  })

  const bars = data?.bars ?? []
  const labels = bars.map(b => b.value)
  const values = bars.map(b => b.count)

  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 120, right: 16, top: 16, bottom: 16 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
    series: [{
      type: 'bar',
      data: values,
      itemStyle: { color: '#8b5cf6' },
      label: { show: true, position: 'right', fontSize: 11 },
    }],
  }

  return (
    <ChartPanel title="Value Counts" subtitle={column} loading={isLoading} error={error ? String(error) : null}>
      <EChart option={option} height={Math.max(240, labels.length * 28 + 40)} />
    </ChartPanel>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────
export const VisualizationStudio: React.FC = () => {
  const { id: datasetId } = useParams<{ id: string }>()
  const [activeChart, setActiveChart] = useState<ChartType>('correlation')
  const [selectedColumn, setSelectedColumn] = useState<string>('')

  const { data: schema } = useQuery({
    queryKey: ['dataset-schema', datasetId],
    queryFn: () => datasetApi.getSchema(datasetId!),
    enabled: !!datasetId,
  })

  const numericColumns: string[] = useMemo(
    () => schema?.columns?.filter((c) => c.inferred_type === 'numeric').map((c) => c.name) ?? [],
    [schema?.columns]
  )
  const categoricalColumns: string[] = useMemo(
    () => schema?.columns?.filter((c) => c.inferred_type === 'categorical').map((c) => c.name) ?? [],
    [schema?.columns]
  )
  const allColumns: string[] = useMemo(
    () => schema?.columns?.map((c) => c.name) ?? [],
    [schema?.columns]
  )

  useEffect(() => {
    if (!selectedColumn && allColumns.length > 0) setSelectedColumn(allColumns[0])
  }, [allColumns, selectedColumn])

  const chartTabs: { key: ChartType; label: string; badge?: string }[] = [
    { key: 'correlation', label: 'Correlation', badge: `${numericColumns.length} cols` },
    { key: 'histogram', label: 'Histogram' },
    { key: 'boxplot', label: 'Boxplot' },
    { key: 'nulls', label: 'Null Map' },
    { key: 'bar', label: 'Value Counts' },
  ]

  if (!datasetId) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        No dataset selected. Open a dataset from the Explorer.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Visualization Studio</h1>
          <p className="mt-1 text-sm text-gray-500">
            {formatNumber(allColumns.length)} columns · {formatNumber(numericColumns.length)} numeric ·{' '}
            {formatNumber(categoricalColumns.length)} categorical
          </p>
        </div>
        <Badge variant="info">
          {schema?.row_count ? `${formatNumber(schema.row_count)} rows` : 'Loading…'}
        </Badge>
      </div>

      {/* Chart type tabs */}
      <div className="flex gap-2 flex-wrap">
        {chartTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveChart(tab.key)}
            className={[
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              activeChart === tab.key
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50',
            ].join(' ')}
          >
            {tab.label}
            {tab.badge && <span className="ml-2 text-xs opacity-70">{tab.badge}</span>}
          </button>
        ))}
      </div>

      {/* Column selector for single-column charts */}
      {(activeChart === 'histogram' || activeChart === 'bar') && (
        <div className="flex items-center gap-3">
          <label htmlFor="col-select" className="text-sm font-medium text-gray-700">
            Column:
          </label>
          <select
            id="col-select"
            value={selectedColumn}
            onChange={(e) => setSelectedColumn(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {(activeChart === 'histogram' ? numericColumns : categoricalColumns).map((col) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Chart area */}
      <div className="min-h-[400px]">
        {activeChart === 'correlation' && <CorrelationHeatmap datasetId={datasetId} />}
        {activeChart === 'histogram' && selectedColumn && (
          <HistogramChart datasetId={datasetId} column={selectedColumn} />
        )}
        {activeChart === 'boxplot' && (
          <BoxplotChart datasetId={datasetId} columns={numericColumns.slice(0, 12)} />
        )}
        {activeChart === 'nulls' && <NullsChart datasetId={datasetId} />}
        {activeChart === 'bar' && selectedColumn && (
          <BarChart datasetId={datasetId} column={selectedColumn} />
        )}
      </div>

      {/* Column overview table */}
      {schema?.columns && (
        <Card>
          <CardHeader
            title="Column Overview"
            subtitle={`${allColumns.length} columns detected`}
          />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 px-3 font-medium text-gray-500">Column</th>
                  <th className="text-left py-2 px-3 font-medium text-gray-500">Type</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-500">Nulls</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-500">Unique</th>
                  <th className="text-left py-2 px-3 font-medium text-gray-500">Action</th>
                </tr>
              </thead>
              <tbody>
                {schema.columns.map((col) => (
                  <tr
                    key={col.name}
                    className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                  >
                    <td className="py-2 px-3 font-mono text-xs text-gray-800">{col.name}</td>
                    <td className="py-2 px-3">
                      <Badge
                        variant={
                          col.inferred_type === 'numeric'
                            ? 'info'
                            : col.inferred_type === 'categorical'
                            ? 'purple'
                            : col.inferred_type === 'datetime'
                            ? 'success'
                            : 'default'
                        }
                      >
                        {col.inferred_type}
                      </Badge>
                    </td>
                    <td className="py-2 px-3 text-right text-gray-600">
                      {col.null_pct != null ? `${col.null_pct.toFixed(1)}%` : '—'}
                    </td>
                    <td className="py-2 px-3 text-right text-gray-600">
                      {col.unique_count != null ? formatNumber(col.unique_count) : '—'}
                    </td>
                    <td className="py-2 px-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setSelectedColumn(col.name)
                          setActiveChart(col.inferred_type === 'numeric' ? 'histogram' : 'bar')
                        }}
                      >
                        Visualize
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

export default VisualizationStudio
