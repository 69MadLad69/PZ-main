// frontend/src/components/ui/index.tsx
import { ReactNode } from 'react';
import { ArrowUpIcon, ArrowDownIcon, MinusIcon } from '@heroicons/react/20/solid';
import { KPIValue } from '../../types';

interface KPICardProps {
  title: string;
  kpi?: KPIValue;
  loading?: boolean;
  icon?: ReactNode;
  color?: string;
}

export function KPICard({ title, kpi, loading, icon, color = '#2E75B6' }: KPICardProps) {
  if (loading) return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-24 mb-3" />
      <div className="h-8 bg-gray-200 rounded w-32" />
    </div>
  );
  const TrendIcon = !kpi?.trend ? null
    : kpi.trend === 'up' ? ArrowUpIcon
    : kpi.trend === 'down' ? ArrowDownIcon
    : MinusIcon;
  const trendColor = kpi?.trend === 'up' ? 'text-green-600'
    : kpi?.trend === 'down' ? 'text-red-500' : 'text-gray-400';

  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <p className="text-sm text-gray-500 font-medium">{title}</p>
        {icon && <div className="p-2 rounded-lg" style={{ background: color + '15' }}>
          <div style={{ color }}>{icon}</div>
        </div>}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-gray-900">
          {kpi?.value?.toLocaleString('uk-UA', { maximumFractionDigits: 1 }) ?? '—'}
        </span>
        <span className="text-sm text-gray-400">{kpi?.unit}</span>
      </div>
      {kpi?.change_pct != null && TrendIcon && (
        <div className={`flex items-center gap-1 mt-1 text-xs ${trendColor}`}>
          <TrendIcon className="w-3 h-3" />
          <span>{Math.abs(kpi.change_pct).toFixed(1)}% проти минулого</span>
        </div>
      )}
    </div>
  );
}

// ── Card wrapper ──────────────────────────────────────────────────────────────
export function Card({ children, title, className = '' }:
  { children: ReactNode; title?: string; className?: string }) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-100 ${className}`}>
      {title && (
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-800">{title}</h3>
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}

// ── Loading spinner ───────────────────────────────────────────────────────────
export function Spinner() {
  return (
    <div className="flex items-center justify-center h-32">
      <div className="w-8 h-8 border-3 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
export function Empty({ message = 'Дані відсутні' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-32 text-gray-400">
      <p className="text-sm">{message}</p>
    </div>
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────────
export function Badge({ children, color = 'gray' }:
  { children: ReactNode; color?: 'gray'|'green'|'blue'|'yellow'|'red' }) {
  const map = {
    gray:   'bg-gray-100 text-gray-700',
    green:  'bg-green-100 text-green-700',
    blue:   'bg-blue-100 text-blue-700',
    yellow: 'bg-yellow-100 text-yellow-700',
    red:    'bg-red-100 text-red-700',
  };
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[color]}`}>{children}</span>;
}
