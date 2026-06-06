// frontend/src/pages/Analytics.tsx
import { useEffect, useState } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
         ResponsiveContainer, Cell } from 'recharts';
import { consumptionApi, weatherApi } from '../services/api';
import { Card, Spinner } from '../components/ui';

export default function Analytics() {
  const [scatter, setScatter] = useState<any[]>([]);
  const [heatmap, setHeatmap] = useState<any[][]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      consumptionApi.getHourly('2025-07-01','2025-07-31',1,1),
      weatherApi.get('2025-07-01','2025-07-31'),
    ]).then(([h, w]) => {
      const hourly = h.data.data ?? [];
      const wMap: Record<string, number> = {};
      (w.data.data ?? []).forEach((r:any) => { wMap[r.timestamp] = r.temperature_c; });
      const sc = hourly.map((r:any) => ({
        temp: wMap[r.timestamp] ?? 20,
        kwh:  r.energy_kwh,
        zone: r.tariff_zone,
      }));
      setScatter(sc);

      // Heatmap: hour x day_of_week
      const hm: number[][] = Array.from({length:24}, ()=>Array(7).fill(0));
      const cnt: number[][] = Array.from({length:24}, ()=>Array(7).fill(0));
      hourly.forEach((r:any) => {
        const ts = new Date(r.timestamp);
        const h2 = ts.getHours(), d = ts.getDay();
        hm[h2][d]  += r.energy_kwh;
        cnt[h2][d] += 1;
      });
      const avg = hm.map((row,h2) => row.map((v,d) => cnt[h2][d] > 0 ? v/cnt[h2][d] : 0));
      setHeatmap(avg);
    }).finally(() => setLoading(false));
  }, []);

  const DAYS = ['Нд','Пн','Вт','Ср','Чт','Пт','Сб'];
  const maxHeat = Math.max(...heatmap.flat(), 1);
  const heat2color = (v: number) => {
    const t = v / maxHeat;
    const r = Math.round(46 + t * (231-46));
    const g = Math.round(117 + t * (74-117));
    const b = Math.round(182 + t * (60-182));
    return `rgb(${r},${g},${b})`;
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Аналітика (ЛР2)</h2>

      <Card title="Споживання vs Температура (Lipень 2025)">
        {loading ? <Spinner /> : (
          <ResponsiveContainer width="100%" height={280}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3"/>
              <XAxis dataKey="temp" name="Температура" unit="°C" tick={{fontSize:11}}/>
              <YAxis dataKey="kwh"  name="Споживання"  unit=" кВт·год" tick={{fontSize:11}}/>
              <Tooltip cursor={{strokeDasharray:'3 3'}}/>
              <Scatter name="Год. споживання" data={scatter}>
                {scatter.map((s,i) => (
                  <Cell key={i} fill={s.zone==='day' ? '#2E75B6' : '#8FAADC'} opacity={0.5}/>
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        )}
      </Card>

      <Card title="Теплова карта: год. споживання (год × день тижня, Lipень 2025)">
        {loading || heatmap.length === 0 ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr>
                  <th className="w-10 text-gray-400">Год</th>
                  {DAYS.map(d => <th key={d} className="text-gray-500 font-medium">{d}</th>)}
                </tr>
              </thead>
              <tbody>
                {heatmap.map((row, h) => (
                  <tr key={h}>
                    <td className="text-gray-400 pr-2 text-right">{h}:00</td>
                    {row.map((v, d) => (
                      <td key={d} title={`${v.toFixed(1)} кВт·год`}
                        style={{ background: heat2color(v) }}
                        className="h-5 border border-white/30 cursor-default" />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center gap-2 mt-3 text-xs text-gray-500">
              <span>Менше</span>
              <div className="flex">
                {[0,.25,.5,.75,1].map(t => (
                  <div key={t} className="w-8 h-3" style={{background: heat2color(t*maxHeat)}}/>
                ))}
              </div>
              <span>Більше</span>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
