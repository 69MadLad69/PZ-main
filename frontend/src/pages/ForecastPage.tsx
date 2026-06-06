// frontend/src/pages/ForecastPage.tsx — final fixed version
import { useEffect, useState } from 'react';
import {
  ComposedChart, Line, Area, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { forecastApi } from '../services/api';
import { Card, Spinner, Empty, KPICard, Badge } from '../components/ui';

export default function ForecastPage() {
  const [summary, setSummary] = useState<any>(null);
  const [hourly, setHourly] = useState<any[]>([]);
  const [testPred, setTestPred] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'forecast' | 'accuracy'>('forecast');

  useEffect(() => {
    Promise.all([
      forecastApi.getSummary(),
      forecastApi.getHourly(168),
      forecastApi.getMetrics(),
      (forecastApi as any).getTestPredictions
        ? (forecastApi as any).getTestPredictions(168)
        : fetch('/api/v1/forecast/test-predictions?n=168').then(r => r.json()),
    ])
      .then(([s, h, m, tp]) => {
        setSummary(s.data ?? s);
        const fc = ((h.data ?? h).data ?? []).map((r: any, i: number) => ({
          i,
          ts: `${Math.floor(i / 24) + 1}д ${String(i % 24).padStart(2, '0')}:00`,
          forecast: +Number(r.predicted_kwh  ?? 0).toFixed(2),
          lower: +Number(r.lower_bound ?? 0).toFixed(2),
          upper: +Number(r.upper_bound ?? 0).toFixed(2),
          solar: +Number(r.solar_kwh ?? 0).toFixed(2),
        }));
        setHourly(fc);
        setMetrics((m.data ?? m).metrics ?? []);
        const raw = (tp.data ?? tp).data ?? [];
        setTestPred(raw.map((r: any, i: number) => ({
          i,
          ts: new Date(r.timestamp).toLocaleString('uk-UA', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }),
          actual: +Number(r.actual_kwh ?? 0).toFixed(2),
          forecast: +Number(r.predicted_kwh ?? 0).toFixed(2),
          error: +Number(r.error_kwh ?? 0).toFixed(2),
        })));
      })
      .catch(err => setError(err?.message ?? 'Помилка'))
      .finally(() => setLoading(false));
  }, []);

  const bestModel = metrics[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-bold text-gray-900">Прогнозування (ЛР2)</h2>
        {bestModel && (
          <div className="flex gap-2">
            <Badge color="blue">
              {bestModel.model ?? bestModel.Модель ?? 'Gradient Boosting'}
            </Badge>
            <Badge color="green">
              MAPE {Number(bestModel.MAPE ?? bestModel['MAPE%'] ?? 0).toFixed(2)}%
            </Badge>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-sm text-yellow-800">
          {error} — виконайте:{' '}
          <code className="bg-yellow-100 px-1 rounded">python -m backend.scripts.train_models</code>
        </div>
      )}

      {bestModel && (
        <Card title="Метрики моделі (тестова вибірка: Листопад–Грудень 2025)">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {([
              ['R²',   Number(bestModel.R2   ?? bestModel['R²']   ?? 0).toFixed(4), '—'],
              ['RMSE', Number(bestModel.RMSE ?? 0).toFixed(4), 'кВт·год'],
              ['MAE',  Number(bestModel.MAE  ?? 0).toFixed(4), 'кВт·год'],
              ['MAPE', Number(bestModel.MAPE ?? bestModel['MAPE%'] ?? 0).toFixed(2) + '%', '—'],
            ] as [string, string, string][]).map(([l, v, u]) => (
              <div key={l} className="bg-blue-50 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-500">{l}</p>
                <p className="font-bold text-xl text-blue-700">{v}</p>
                {u !== '—' && <p className="text-xs text-gray-400">{u}</p>}
              </div>
            ))}
          </div>
        </Card>
      )}

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KPICard title="Прогноз місяця" kpi={{ value: summary.monthly_kwh, unit: 'кВт·год' }} />
          <KPICard title="Вартість" kpi={{ value: summary.monthly_cost_uah, unit: 'грн' }} />
          <KPICard title="Економія СЕС" kpi={{ value: summary.solar_saving_uah, unit: 'грн' }} />
          <KPICard title="Питоме" kpi={{ value: summary.specific_kwh_m2,  unit: 'кВт·год/м²' }} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2">
        {(['forecast', 'accuracy'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              tab === t ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}>
            {t === 'forecast' ? 'Прогноз + довірчий інтервал' : 'Факт vs Прогноз'}
          </button>
        ))}
      </div>

      {tab === 'forecast' && (
        <Card title="Прогноз Листопада 2025 (168 год) з довірчим інтервалом ±1.5σ">
          {loading ? <Spinner /> : hourly.length === 0 ? <Empty message="Модель не завантажена" /> : (
            <>
              <ResponsiveContainer width="100%" height={340}>
                <ComposedChart data={hourly} margin={{ top: 5, right: 15, bottom: 40, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="ts" tick={{ fontSize: 8 }} interval={23}
                    angle={-30} textAnchor="end" height={55} />
                  <YAxis tick={{ fontSize: 11 }}
                    label={{ value: 'кВт·год', angle: -90, position: 'insideLeft', fontSize: 10 }} />
                  <Tooltip formatter={(v: number, name: string) => [v?.toFixed(2) + ' кВт·год', name]} />
                  <Legend verticalAlign="top" wrapperStyle={{ paddingBottom: 8 }} />
                  {/* CI band */}
                  <Area dataKey="upper" name=" " stroke="none" fill="#DBEAFE" fillOpacity={0.7} legendType="none" />
                  <Area dataKey="lower" name="Довірчий інтервал" stroke="#93C5FD"
                    strokeWidth={1} strokeDasharray="3 2" fill="white" fillOpacity={1} />
                  {/* Solar */}
                  <Area dataKey="solar" name="Генерація СЕС" stroke="#F39C12"
                    fill="#FEF3C7" fillOpacity={0.6} strokeWidth={1.5} />
                  {/* Forecast */}
                  <Line dataKey="forecast" name="Прогноз (GB)" stroke="#2E75B6"
                    dot={false} strokeWidth={2} />
                  {/* Upper CI line */}
                  <Line dataKey="upper" name=" " stroke="#93C5FD" dot={false}
                    strokeWidth={1} strokeDasharray="4 2" legendType="none" />
                </ComposedChart>
              </ResponsiveContainer>
              <p className="text-xs text-gray-400 mt-1">
                Синя лінія — прогноз Gradient Boosting (листопад 2025).
                Блакитна смуга — довірчий інтервал ±1.5 × RMSE.
                Жовта — очікувана генерація СЕС 35 кВт.
              </p>
            </>
          )}
        </Card>
      )}
      {tab === 'accuracy' && (
        <Card title="Факт vs Прогноз (тестовий набір Листопада 2025, перші 168 год)">
          {loading ? <Spinner /> : testPred.length === 0
            ? <Empty message="Дані тестових передбачень відсутні" />
            : (
              <>
                <ResponsiveContainer width="100%" height={340}>
                  <ComposedChart data={testPred} margin={{ top: 5, right: 30, bottom: 40, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="ts" tick={{ fontSize: 8 }} interval={23}
                      angle={-30} textAnchor="end" height={55} />
                    <YAxis yAxisId="main" tick={{ fontSize: 11 }} />
                    <YAxis yAxisId="err" orientation="right" tick={{ fontSize: 10 }}
                      label={{ value: 'Похибка', angle: 90, position: 'insideRight', fontSize: 10 }} />
                    <Tooltip formatter={(v: number, name: string) => [v?.toFixed(2) + ' кВт·год', name]} />
                    <Legend verticalAlign="top" />
                    <Area yAxisId="main" dataKey="actual" name=" " stroke="none" fill="#FEE2E2" fillOpacity={0.4} legendType="none" />
                    <Line yAxisId="main" type="monotone" dataKey="actual"
                      name="Фактичне" stroke="#E74C3C" dot={false} strokeWidth={2} />
                    <Line yAxisId="main" type="monotone" dataKey="forecast"
                      name="Прогноз (GB)" stroke="#2E75B6" dot={false}
                      strokeWidth={2} strokeDasharray="5 3" />
                    <Bar yAxisId="err" dataKey="error" name="Абс. похибка"
                      fill="#F39C12" opacity={0.45} />
                  </ComposedChart>
                </ResponsiveContainer>
                <p className="text-xs text-gray-400 mt-1">
                  Червона — фактичне споживання (ЛР1 measurements).
                  Синя пунктирна — прогноз GB з реальними лаговими ознаками.
                  Помаранчеві стовпці — абсолютна погодинна похибка.
                </p>
              </>
          )}
        </Card>
      )}
    </div>
  );
}
