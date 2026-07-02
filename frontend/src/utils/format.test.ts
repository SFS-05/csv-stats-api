import { describe, expect, it } from 'vitest';
import { formatBytes, formatDuration, formatFileFormat, formatNumber, formatPct, getStatusBadgeClass, getStatusColor } from './format';

describe('format utilities', () => {
  it('formats common display values consistently', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1024)).toBe('1 KB');
    expect(formatNumber(1234567)).toBe('1,234,567');
    expect(formatPct(12.345, 2)).toBe('12.35%');
    expect(formatFileFormat('csv')).toBe('CSV');
  });

  it('formats durations for jobs', () => {
    expect(formatDuration(null)).toBe('—');
    expect(formatDuration(2.345)).toBe('2.3s');
    expect(formatDuration(125)).toBe('2m 5s');
    expect(formatDuration(3661)).toBe('1h 1m');
  });

  it('maps known and unknown statuses to stable classes', () => {
    expect(getStatusColor('ready')).toBe('text-green-400');
    expect(getStatusBadgeClass('failed')).toContain('text-red-400');
    expect(getStatusColor('unknown')).toBe('text-gray-400');
    expect(getStatusBadgeClass('unknown')).toContain('text-gray-400');
  });
});
