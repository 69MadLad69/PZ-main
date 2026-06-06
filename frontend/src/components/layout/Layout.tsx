// frontend/src/components/layout/Layout.tsx
import { Outlet, NavLink } from 'react-router-dom';
import {
  HomeIcon, ChartBarIcon, BoltIcon, CpuChipIcon,
  ArrowsRightLeftIcon, PresentationChartLineIcon,
  DocumentChartBarIcon,
} from '@heroicons/react/24/outline';

const nav = [
  { to: '/dashboard', icon: HomeIcon, label: 'Dashboard' },
  { to: '/consumption', icon: ChartBarIcon, label: 'Споживання' },
  { to: '/forecast', icon: PresentationChartLineIcon, label: 'Прогноз' },
  { to: '/ems', icon: CpuChipIcon, label: 'EMS' },
  { to: '/energy-balance', icon: ArrowsRightLeftIcon, label: 'Енергобаланс' },
  { to: '/analytics', icon: BoltIcon, label: 'Аналітика' },
  { to: '/reports', icon: DocumentChartBarIcon, label: 'Звіти' },
];

export default function Layout() {
  return (
    <div className="flex h-screen bg-gray-50 font-sans">
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col shadow-sm">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
              <BoltIcon className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-bold text-gray-900 text-sm">EMS</p>
              <p className="text-xs text-gray-500">Поліклініка</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors
                 ${isActive
                   ? 'bg-primary-50 text-primary-700 font-medium'
                   : 'text-gray-600 hover:bg-gray-100'}`
              }>
              <Icon className="w-5 h-5 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-200">
          <p className="text-xs text-gray-400">ЛР1–ЛР4 · Київ 2025</p>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">
            Система енергоменеджменту поліклініки
          </h1>
          <div className="flex items-center gap-3 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              PostgreSQL
            </span>
            <span>850 м² · 95 кВт · 08:00–20:00</span>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
