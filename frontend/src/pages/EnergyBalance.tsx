import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid,
         Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { emsApi } from '../services/api';
import { Card, Spinner, Empty } from '../components/ui';
import type { EnergyFlow } from '../types';

function FlowDiagram({ flow }: { flow: EnergyFlow }) {
  const total = Math.max(flow.solar_to_load + flow.battery_to_load + flow.grid_to_load, 1);

  const TOTAL_H = 260;
  const GAP = 16;
  const hSolar  = Math.max(20, (flow.solar_to_load   / total) * TOTAL_H * 0.85);
  const hBat = Math.max(20, (flow.battery_to_load / total) * TOTAL_H * 0.85);
  const hGrid = Math.max(20, (flow.grid_to_load    / total) * TOTAL_H * 0.85);

  const ySolar = GAP;
  const yBat = ySolar + hSolar + GAP;
  const yGrid  = yBat   + hBat   + GAP;

  const BOX_W = 80;
  const SRC_X = 10;
  const DST_X = 380;
  const DST_Y = TOTAL_H / 2 - 25;
  const DST_H = 50;

  const pct = (v: number) => total > 0 ? (v / total * 100).toFixed(1) + '%' : '0%';

  const renderFlow = (
    color: string, srcY: number, srcH: number,
    dstY: number, dstH: number, label: string, value: number,
  ) => {
    const srcMidY = srcY + srcH / 2;
    const dstMidY = dstY + dstH / 2;
    const ctrl1X = SRC_X + BOX_W + 80;
    const ctrl2X = DST_X - 80;
    const midLabelX = (SRC_X + BOX_W + DST_X) / 2;
    const midLabelY = (srcMidY + dstMidY) / 2;
    const w = Math.max(2, srcH * 0.6);

    return (
      <g key={label}>
        <path
          d={`M ${SRC_X + BOX_W} ${srcMidY - w/2}
              C ${ctrl1X} ${srcMidY - w/2}, ${ctrl2X} ${dstMidY - w/2}, ${DST_X} ${dstMidY - w/2}
              L ${DST_X} ${dstMidY + w/2}
              C ${ctrl2X} ${dstMidY + w/2}, ${ctrl1X} ${srcMidY + w/2}, ${SRC_X + BOX_W} ${srcMidY + w/2} Z`}
          fill={color} opacity={0.35}
        />
        <text x={midLabelX} y={midLabelY - 2}
          textAnchor="middle" fontSize="9" fill={color} fontWeight="600">
          {value.toFixed(1)} кВт·год
        </text>
        <text x={midLabelX} y={midLabelY + 9}
          textAnchor="middle" fontSize="8" fill={color} opacity={0.8}>
          {pct(value)}
        </text>
      </g>
    );
  };

  return (
    <svg viewBox={`0 0 520 ${TOTAL_H + GAP * 2}`} className="w-full max-h-72">
      <rect x={SRC_X} y={ySolar} width={BOX_W} height={hSolar} rx="6" fill="#F39C12" />
      <text x={SRC_X+BOX_W/2} y={ySolar+hSolar/2-4} textAnchor="middle" fill="white" fontSize="11" fontWeight="bold">СЕС</text>
      <text x={SRC_X+BOX_W/2} y={ySolar+hSolar/2+8} textAnchor="middle" fill="white" fontSize="9">{flow.solar_to_load.toFixed(1)}</text>

      <rect x={SRC_X} y={yBat} width={BOX_W} height={hBat} rx="6" fill="#8E44AD" />
      <text x={SRC_X+BOX_W/2} y={yBat+hBat/2-4} textAnchor="middle" fill="white" fontSize="11" fontWeight="bold">BESS</text>
      <text x={SRC_X+BOX_W/2} y={yBat+hBat/2+8} textAnchor="middle" fill="white" fontSize="9">{flow.battery_to_load.toFixed(1)}</text>

      <rect x={SRC_X} y={yGrid} width={BOX_W} height={hGrid} rx="6" fill="#64748B" />
      <text x={SRC_X+BOX_W/2} y={yGrid+hGrid/2-4} textAnchor="middle" fill="white" fontSize="11" fontWeight="bold">Мережа</text>
      <text x={SRC_X+BOX_W/2} y={yGrid+hGrid/2+8} textAnchor="middle" fill="white" fontSize="9">{flow.grid_to_load.toFixed(1)}</text>

      <rect x={DST_X} y={DST_Y} width={BOX_W+10} height={DST_H} rx="6" fill="#2E75B6" />
      <text x={DST_X+(BOX_W+10)/2} y={DST_Y+DST_H/2-5} textAnchor="middle" fill="white" fontSize="10" fontWeight="bold">Навантаження</text>
      <text x={DST_X+(BOX_W+10)/2} y={DST_Y+DST_H/2+8} textAnchor="middle" fill="white" fontSize="9">{total.toFixed(1)} кВт·год</text>

      {renderFlow("#F39C12", ySolar, hSolar, DST_Y, DST_H, "solar", flow.solar_to_load)}
      {renderFlow("#8E44AD", yBat, hBat, DST_Y, DST_H, "batt",  flow.battery_to_load)}
      {renderFlow("#64748B", yGrid, hGrid, DST_Y, DST_H, "grid",  flow.grid_to_load)}

      <text x={SRC_X} y={TOTAL_H + GAP*2 - 2} fontSize="9" fill="#888">
        Ширина потоку пропорційна частці енергії
      </text>
    </svg>
  );
}

export default function EnergyBalance() {
  const [flow, setFlow] = useState<EnergyFlow | null>(null);
  const [sim, setSim] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([emsApi.getEnergyFlow(), emsApi.getSimulation()])
      .then(([f, s]) => {
        setFlow(f.data);
        const days: Record<string, any> = {};
        (s.data.data ?? []).forEach((r: any) => {
          const d = r.timestamp?.slice(0, 10) ?? '';
          if (!days[d]) days[d] = { day: d.slice(5), solar: 0, battery: 0, grid: 0, load: 0 };
          days[d].solar += r.solar_kwh ?? 0;
          days[d].battery += r.discharge_kwh ?? 0;
          days[d].grid += r.import_kwh  ?? 0;
          days[d].load += r.load_kwh ?? 0;
        });
        setSim(Object.values(days));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Енергетичний баланс (ЛР3)</h2>
      <Card title="Потоки енергії (Energy Flow Diagram)">
        {loading ? <Spinner /> : !flow ? (
          <Empty message="Спочатку запустіть симуляцію: python -m backend.scripts.run_simulation" />
        ) : (
          <FlowDiagram flow={flow} />
        )}
      </Card>

      {!loading && flow && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[
            ['СЕС → Навантаження', flow.solar_to_load, '#F39C12'],
            ['BESS → Навантаження', flow.battery_to_load, '#8E44AD'],
            ['Мережа → Навантаження',flow.grid_to_load, '#64748B'],
            ['СЕС → BESS', flow.solar_to_battery, '#F39C12'],
            ['Мережа → BESS', flow.grid_to_battery, '#64748B'],
            ['СЕС → Мережа', flow.solar_to_grid, '#27AE60'],
          ].map(([l, v, c]) => (
            <div key={l as string}
              className="bg-white rounded-lg p-3 border-l-4 text-sm"
              style={{ borderLeftColor: c as string }}>
              <p className="text-gray-500 text-xs">{l}</p>
              <p className="font-bold text-gray-900">{(v as number).toFixed(1)} кВт·год</p>
            </div>
          ))}
        </div>
      )}

      <Card title="Добовий баланс джерел (7 діб симуляції)">
        {loading ? <Spinner /> : sim.length === 0 ? (
          <Empty message="Запустіть симуляцію" />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={sim}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }}
                label={{ value: 'кВт·год', angle: -90, position: 'insideLeft', fontSize: 10 }} />
              <Tooltip formatter={(v: number) => [`${v.toFixed(1)} кВт·год`]} />
              <Legend />
              <Bar dataKey="solar" name="СЕС" stackId="a" fill="#F39C12" />
              <Bar dataKey="battery" name="BESS" stackId="a" fill="#8E44AD" />
              <Bar dataKey="grid" name="Мережа" stackId="a" fill="#64748B" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  );
}