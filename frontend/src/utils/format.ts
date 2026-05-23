/**
 * Formatting utilities for numbers, bytes, dates, and percentages.
 */

export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('en-US').format(n);
}

export function formatPct(n: number, decimals = 1): string {
  return `${n.toFixed(decimals)}%`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

export function formatFileFormat(fmt: string): string {
  return fmt.toUpperCase();
}

export function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    ready: 'text-green-400',
    success: 'text-green-400',
    processing: 'text-yellow-400',
    started: 'text-yellow-400',
    queued: 'text-blue-400',
    failed: 'text-red-400',
    failure: 'text-red-400',
    revoked: 'text-gray-400',
    pending: 'text-gray-400',
    uploaded: 'text-blue-400',
  };
  return map[status] ?? 'text-gray-400';
}

export function getStatusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    ready: 'bg-green-900/50 text-green-400 border-green-800',
    success: 'bg-green-900/50 text-green-400 border-green-800',
    processing: 'bg-yellow-900/50 text-yellow-400 border-yellow-800',
    started: 'bg-yellow-900/50 text-yellow-400 border-yellow-800',
    queued: 'bg-blue-900/50 text-blue-400 border-blue-800',
    failed: 'bg-red-900/50 text-red-400 border-red-800',
    failure: 'bg-red-900/50 text-red-400 border-red-800',
    revoked: 'bg-gray-800 text-gray-400 border-gray-700',
    pending: 'bg-gray-800 text-gray-400 border-gray-700',
  };
  return map[status] ?? 'bg-gray-800 text-gray-400 border-gray-700';
}