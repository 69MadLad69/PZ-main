// frontend/src/pages/Dashboard.tsx
import { useEffect, useState } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import {
  BoltIcon, SunIcon, Battery100Icon, BanknotesIcon,
  ArrowTrendingUpIcon, GlobeEuropeAfricaIcon,
} from '@heroicons/react/24/outline';
import { dashboardApi, consumptionApi } from '../services/api';
import { KPICard, Card, Spinner, Empty } from '../components/ui';
import { DashboardSummary, MonthlyConsumption } from '../types';

const MONTHS_UA = ['Січ','Лют','Бер','Кві','Тра','Чер','Лип','Сер','Вер','Жов','Лис','Гру'];

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [monthly, setMonthly] = useState<MonthlyConsumption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      dashboardApi.getSummary(2025),
      consumptionApi.getMonthly(2025),
    ]).then(([s, m]) => {
      setSummary(s.data);
      setMonthly(m.data.data ?? []);
    }).catch(err => {
      setError(err.response?.data?.detail ?? err.message);
    }).finally(() => setLoading(false));
  }, []);

  const monthlyChart = monthly.map(m => ({
    name: MONTHS_UA[m.month - 1],
    День: +(m.day_kwh   / 1000).toFixed(1),
    Ніч: +(m.night_kwh / 1000).toFixed(1),
    Ціна: +(m.total_cost_uah / 1000).toFixed(1),
  }));

  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700">
      <p className="font-semibold">Помилка завантаження</p>
      <p className="text-sm mt-1">{error}</p>
      <p className="text-sm mt-2 text-red-500">Переконайтесь, що FastAPI запущено: uvicorn backend.main:app --reload</p>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">Панель моніторингу</h2>
        {summary && (
          <p className="text-sm text-gray-400">
            Оновлено: {new Date(summary.last_updated).toLocaleString('uk-UA')}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard title="Поточне споживання" kpi={summary?.current_consumption_kw} loading={loading}
          icon={<BoltIcon className="w-5 h-5" />} color="#2E75B6" />
        <KPICard title="Генерація СЕС (місяць)" kpi={summary?.solar_generation_kwh} loading={loading}
          icon={<SunIcon className="w-5 h-5" />} color="#F39C12" />
        <KPICard title="Заряд батареї" kpi={summary?.battery_soc_pct} loading={loading}
          icon={<Battery100Icon className="w-5 h-5" />}  color="#8E44AD" />
        <KPICard title="Покриття СЕС" kpi={summary?.solar_coverage_pct} loading={loading}
          icon={<ArrowTrendingUpIcon className="w-5 h-5" />} color="#27AE60" />
        <KPICard title="Споживання (місяць)" kpi={summary?.month_consumption_kwh} loading={loading}
          icon={<BoltIcon className="w-5 h-5" />} color="#2E75B6" />
        <KPICard title="Економія від EMS" kpi={summary?.cost_savings_uah} loading={loading}
          icon={<BanknotesIcon className="w-5 h-5" />}   color="#27AE60" />
        <KPICard title="Зниження CO₂" kpi={summary?.co2_reduction_kg} loading={loading}
          icon={<GlobeEuropeAfricaIcon className="w-5 h-5" />} color="#1F8B8B" />
        <KPICard title="Споживання за добу" kpi={summary?.today_consumption_kwh} loading={loading}
          icon={<BoltIcon className="w-5 h-5" />} color="#2E75B6" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="Місячне споживання 2025 (МВт·год)" className="lg:col-span-2">
          {loading ? <Spinner /> : monthlyChart.length === 0 ? <Empty /> : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={monthlyChart} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit=" МВт" />
                <Tooltip formatter={(v: number) => [`${v} МВт·год`]} />
                <Legend />
                <Bar dataKey="День" stackId="a" fill="#2E75B6" radius={[0,0,0,0]} />
                <Bar dataKey="Ніч"  stackId="a" fill="#8FAADC" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title="Вартість (тис. грн/міс)">
          {loading ? <Spinner /> : monthlyChart.length === 0 ? <Empty /> : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={monthlyChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} unit="к" />
                <Tooltip formatter={(v: number) => [`${v} тис. грн`]} />
                <Area type="monotone" dataKey="Ціна" stroke="#E74C3C" fill="#FDEDEC" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <Card title="Параметри системи">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          {[
            ['Об\'єкт', 'Поліклініка Київ'],
            ['Площа', '850 м²'],
            ['СЕС', '35 кВт'],
            ['BESS', '25 кВт·год'],
            ['Тариф (день)', '6,90 грн/кВт·год'],
            ['Тариф (ніч)', '5,60 грн/кВт·год'],
            ['Режим роботи', '08:00–20:00'],
            ['Лічильники', '6 (рівні 1–3)'],
          ].map(([label, value]) => (
            <div key={label} className="bg-gray-50 rounded-lg p-3">
              <p className="text-gray-500 text-xs">{label}</p>
              <p className="font-semibold text-gray-900">{value}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
