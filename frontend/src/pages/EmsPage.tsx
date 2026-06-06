import { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { emsApi } from '../services/api';
import { Card, Spinner, KPICard } from '../components/ui';
import type { EnergyMetrics, EconomicMetrics } from '../types';

export default function EmsPage() {
  const [status, setStatus] = useState<any>(null);
  const [sim, setSim] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<EnergyMetrics | null>(null);
  const [economics, setEconomics] = useState<EconomicMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    emsApi.getStatus()
      .then(r => setStatus(r.data))
      .catch(() => setStatus({ status: 'no_runs' }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const runId = status?.run_id;
    if (!runId) return;

    setLoadingDetails(true);
    Promise.all([
      emsApi.getSimulation(runId),
      emsApi.getMetrics(runId),
      emsApi.getEconomics(runId),
    ])
      .then(([s, m, e]) => {
        setSim(
          (s.data.data ?? []).map((r: any) => ({
            ...r,
            ts: new Date(r.timestamp).toLocaleString('uk-UA', {
              month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
            }),
          }))
        );
        setMetrics(m.data);
        setEconomics(e.data);
      })
      .catch(console.error)
      .finally(() => setLoadingDetails(false));
  }, [status?.run_id]);

  const handleRun = async () => {
    setRunning(true);
    try {
      await emsApi.runSimulation('2025-07-01', 7);
      let n = 0;
      const t = setInterval(async () => {
        n++;
        const r = await emsApi.getStatus().catch(() => null);
        if (r?.data?.run_id || n > 30) {
          clearInterval(t);
          setStatus(r?.data ?? { status: 'no_runs' });
          setRunning(false);
        }
      }, 3000);
    } catch (err: any) {
      setRunning(false);
      alert(err?.response?.data?.detail ?? err?.message ?? 'Помилка');
    }
  };

  if (loading) return <div className="flex items-center justify-center h-48"><Spinner /></div>;

  const hasRun = Boolean(status?.run_id);

  return (
    <div className="space-y-6">

      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-bold text-gray-900">
          EMS — Система управління енергопотоками (ЛР3)
        </h2>
        <div className="flex items-center gap-3">
          {hasRun && (
            <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs font-medium">
              {status.status}
            </span>
          )}
          <button
            onClick={handleRun}
            disabled={running}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-colors"
          >
            {running ? 'Виконується...' : hasRun ? 'Перезапустити' : 'Запустити симуляцію'}
          </button>
        </div>
      </div>

      {!hasRun && !running && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6">
          <p className="font-semibold text-amber-900 mb-2">Симуляція ще не запускалась</p>
          <p className="text-sm text-amber-700 mb-3">
            Натисни «Запустити симуляцію» вище або виконай у терміналі:
          </p>
          <code className="block bg-amber-100 text-amber-900 text-xs px-3 py-2 rounded">
            python -m backend.scripts.run_simulation --start 2025-07-01 --days 7
          </code>
        </div>
      )}

      {running && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center gap-3">
          <Spinner />
          <p className="text-blue-700 text-sm">
            Симуляція виконується (168 кроків × 7 діб)… Сторінка оновиться автоматично.
          </p>
        </div>
      )}

      {hasRun && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            {[
              ['Run ID', status.run_id ?? '—'],
              ['Стратегія', status.strategy ?? '—'],
              ['Споживання', `${Number(status.total_consumption_kwh ?? 0).toLocaleString()} кВт·год`],
              ['Економія', `${Number(status.savings_uah ?? 0).toLocaleString()} грн`],
            ].map(([l, v]) => (
              <div key={l} className="bg-white rounded-lg p-3 border border-gray-100">
                <p className="text-gray-400 text-xs">{l}</p>
                <p className="font-semibold text-gray-900">{v}</p>
              </div>
            ))}
          </div>

          {loadingDetails && <Spinner />}
          {!loadingDetails && metrics && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {([
                ['Покриття СЕС', metrics.solar_coverage_pct, '%'],
                ['Самоспоживання СЕС', metrics.self_consumption_pct, '%'],
                ['Самодостатність', metrics.self_sufficiency_pct, '%'],
                ['Цикли батареї', metrics.battery_cycles, 'цикл.'],
              ] as [string, number, string][]).map(([title, value, unit]) => (
                <KPICard key={title} title={title} kpi={{ value, unit }} />
              ))}
            </div>
          )}

          {!loadingDetails && sim.length > 0 && (
            <Card title="SOC батареї та енергобаланс (168 год)">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={sim}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f5" />
                  <XAxis dataKey="ts" tick={{ fontSize: 9 }} interval={11}
                    angle={-30} textAnchor="end" height={50} />
                  <YAxis yAxisId="soc" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                  <YAxis yAxisId="kw"  orientation="right" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Line yAxisId="soc" dataKey="soc_pct" name="SOC %" stroke="#8E44AD" dot={false} strokeWidth={2} />
                  <Line yAxisId="kw" dataKey="solar_kwh" name="СЕС" stroke="#F39C12" dot={false} />
                  <Line yAxisId="kw" dataKey="import_kwh" name="Імпорт" stroke="#E74C3C" dot={false} />
                  <Line yAxisId="kw" dataKey="discharge_kwh" name="Розряд" stroke="#27AE60" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}

          {!loadingDetails && economics && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card title="Економічний результат">
                {([
                  ['Вартість з EMS', `${economics.ems_cost_uah.toLocaleString()} грн`],
                  ['Вартість без EMS', `${economics.baseline_cost_uah.toLocaleString()} грн`],
                  ['Економія', `${economics.savings_uah.toLocaleString()} грн (${economics.savings_pct.toFixed(1)}%)`],
                  ['Річна економія', `${economics.annual_savings_uah.toLocaleString()} грн/рік`],
                ] as [string, string][]).map(([l, v]) => (
                  <div key={l} className="flex justify-between py-1.5 border-b border-gray-50 last:border-0 text-sm">
                    <span className="text-gray-500">{l}</span>
                    <span className="font-semibold">{v}</span>
                  </div>
                ))}
              </Card>
              <Card title="Інвестиційний аналіз">
                {([
                  ['CAPEX', `${economics.capex_total_uah.toLocaleString()} грн`],
                  ['Simple Payback', `${economics.simple_payback_years.toFixed(1)} р.`],
                  ['NPV (r=12%, 20р.)', `${economics.npv_uah.toLocaleString()} грн`],
                  ['IRR', `${economics.irr_pct.toFixed(1)}%`],
                  ['LCOE', `${economics.lcoe_uah_kwh.toFixed(2)} грн/кВт·год`],
                ] as [string, string][]).map(([l, v]) => (
                  <div key={l} className="flex justify-between py-1.5 border-b border-gray-50 last:border-0 text-sm">
                    <span className="text-gray-500">{l}</span>
                    <span className={`font-semibold ${l.includes('NPV') && economics.npv_uah < 0 ? 'text-red-600' : ''}`}>{v}</span>
                  </div>
                ))}
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
