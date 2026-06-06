import { useEffect, useState } from 'react';
import {
  ComposedChart, Line, Bar, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { consumptionApi } from '../services/api';
import { Card, Spinner, Empty } from '../components/ui';
import GaugeComponent from 'react-gauge-component';

type Period = 'monthly' | 'weekly' | 'daily';
const MONTHS_UA = ['Сiч','Лют','Бер','Квi','Тра','Чер','Лип','Сер','Вер','Жов','Лис','Гру'];

function FilterLegend({ items, visible, onToggle }:
  { items:{key:string;label:string;color:string}[]; visible:Set<string>; onToggle:(k:string)=>void }) {
  return (
    <div className="flex flex-wrap gap-2 mb-3">
      {items.map(({ key, label, color }) => (
        <button key={key} onClick={() => onToggle(key)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all ${
            visible.has(key) ? 'text-white border-transparent' : 'border-gray-300 bg-white text-gray-400'
          }`}
          style={{ backgroundColor: visible.has(key) ? color : undefined }}>
          <span className="w-2 h-2 rounded-full"
            style={{ backgroundColor: visible.has(key) ? 'white' : color }} />
          {label}
        </button>
      ))}
    </div>
  );
}

export default function Consumption() {
  const [period, setPeriod]  = useState<Period>('monthly');
  const [monthly, setMonthly] = useState<any[]>([]);
  const [daily, setDaily]   = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [visible, setVisible] = useState(new Set(['day','night','total','baseline','cost']));

  useEffect(() => {
    Promise.all([
      consumptionApi.getMonthly(2025),
      consumptionApi.getDaily('2025-07-01','2025-07-31'),
    ]).then(([m, d]) => {
      setMonthly((m.data.data ?? []).map((r: any) => ({
        ...r,
        name: MONTHS_UA[r.month - 1],
        baseline: +(r.total_kwh * 0.85).toFixed(1),
      })));
      setDaily((d.data.data ?? []).map((r: any) => ({
        ...r,
        name: r.day?.slice(5) ?? '',
        baseline: +(r.total_kwh * 0.85).toFixed(1),
      })));
    }).finally(() => setLoading(false));
  }, []);

  const toggle = (k: string) => {
    const n = new Set(visible); n.has(k) ? n.delete(k) : n.add(k); setVisible(n);
  };

  const weekly = daily.reduce((acc: any[], r, i) => {
    const wk = Math.floor(i / 7);
    if (!acc[wk]) acc[wk] = { name: `Тижд.${wk+1}`, total_kwh:0, baseline:0, cost_uah:0 };
    acc[wk].total_kwh += r.total_kwh || 0;
    acc[wk].baseline  += r.baseline  || 0;
    acc[wk].cost_uah  += r.cost_uah  || 0;
    return acc;
  }, []);

  const data = period==='monthly' ? monthly : period==='weekly' ? weekly : daily;
  const isMonthly = period === 'monthly';

  const LEGEND = isMonthly
    ? [
        { key:'day', label:'Денна зона', color:'#2E75B6' },
        { key:'night', label:'Нічна зона', color:'#8FAADC' },
        { key:'baseline', label:'Базова лінія', color:'#E74C3C' },
      ]
    : [
        { key:'total', label:'Споживання', color:'#2E75B6' },
        { key:'baseline', label:'Базова лінія', color:'#E74C3C' },
      ];
  

  const annualConsumption = monthly.reduce((s, r) => s + r.total_kwh, 0);

  const annualCost = monthly.reduce((s, r) => s + r.total_cost_uah, 0);

  const averageMonth =
    monthly.length > 0
      ? annualConsumption / monthly.length
      : 0;

  const efficiency = 85;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-bold text-gray-900">Споживання (ЛР1)</h2>
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
          {(['monthly','weekly','daily'] as Period[]).map(p => (
            <button key={p} onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                period===p ? 'bg-white text-blue-700 font-semibold shadow-sm' : 'text-gray-600 hover:bg-gray-200'
              }`}>
              {p==='monthly'?'Рік':p==='weekly'?'Тижні':'Дні'}
            </button>
          ))}
        </div>
      </div>

      <Card title={`Споживання + базова лінія (${isMonthly?'2025 рік':period==='weekly'?'тижні Липня':'Липень 2025'})`}>
        <FilterLegend items={LEGEND} visible={visible} onToggle={toggle}/>
        {loading ? <Spinner/> : data.length===0 ? <Empty/> : (
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={data} margin={{ top:5, right:10, bottom: period==='daily'?40:20, left:0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0"/>
              <XAxis dataKey="name" tick={{fontSize:11}}
                angle={period==='daily'?-45:0} textAnchor={period==='daily'?'end':'middle'}
                height={period==='daily'?50:25}/>
              <YAxis tick={{fontSize:11}}
                label={{value:'кВт·год',angle:-90,position:'insideLeft',fontSize:10}}/>
              <Tooltip formatter={(v:number,n:string)=>[`${v?.toLocaleString()} кВт·год`,n]}/>
              {isMonthly && visible.has('day')   && <Bar dataKey="day_kwh"   name="Денна зона" stackId="a" fill="#2E75B6"/>}
              {isMonthly && visible.has('night') && <Bar dataKey="night_kwh" name="Нічна зона" stackId="a" fill="#8FAADC" radius={[3,3,0,0]}/>}
              {!isMonthly && visible.has('total') && <Bar dataKey="total_kwh" name="Споживання" fill="#2E75B6" radius={[3,3,0,0]}/>}
              {visible.has('baseline') && (
                <Line type="monotone" dataKey="baseline" name="Базова лінія (85%)"
                  stroke="#E74C3C" strokeDasharray="6 3" strokeWidth={2} dot={false}/>
              )}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </Card>

      <Card title="Вартість (грн)">
        {loading ? <Spinner/> : data.length===0 ? <Empty/> : (
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0"/>
              <XAxis dataKey="name" tick={{fontSize:11}}/>
              <YAxis tick={{fontSize:11}} tickFormatter={(v:number)=>v>=1000?`${(v/1000).toFixed(0)}к`:String(v)}/>
              <Tooltip formatter={(v:number)=>[`${v?.toLocaleString()} грн`]}/>
              <Area type="monotone"
                dataKey={isMonthly?'total_cost_uah':'cost_uah'}
                name="Вартість" stroke="#F39C12" fill="#FEF3C7" strokeWidth={2}/>
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </Card>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card title="Завантаження">
          <GaugeComponent
            value={72}
            minValue={0}
            maxValue={100}
            labels={{
              valueLabel: {
                formatTextValue: value => `${value}%`
              }
            }}
          />
        </Card>

        <Card title="Енергоефективність">
          <GaugeComponent
            value={efficiency}
            minValue={0}
            maxValue={100}
            arc={{
              subArcs: [
                { limit: 40, color: '#E74C3C' },
                { limit: 70, color: '#F39C12' },
                { color: '#27AE60' },
              ]
            }}
            labels={{
              valueLabel: {
                formatTextValue: value => `${value}%`
              }
            }}
          />
        </Card>

        <Card title="Середнє за місяць">
        <GaugeComponent
          value={averageMonth}
          minValue={6000}
          maxValue={12000}
          arc={{
            subArcs: [
              { limit: 8000, color: '#27AE60' },
              { limit: 10000, color: '#F39C12' },
              { color: '#E74C3C' }
            ]
          }}
          labels={{
            valueLabel: {
              formatTextValue: value =>
                `${Math.round(Number(value))}`
            }
          }}
        />
      </Card>

      <Card title="Річна вартість">
        <GaugeComponent
          value={annualCost}
          minValue={0}
          maxValue={1000000}
          arc={{
            subArcs: [
              { limit: 400000, color: '#27AE60' },
              { limit: 700000, color: '#F39C12' },
              { color: '#E74C3C' }
            ]
          }}
          labels={{
            valueLabel: {
              formatTextValue: value =>
                `${Math.round(Number(value))} грн`
            }
          }}
        />
      </Card>
      </div>        

      {!loading && monthly.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          {([
            ['Річне споживання', `${monthly.reduce((s,r)=>s+r.total_kwh,0).toLocaleString('uk-UA',{maximumFractionDigits:0})} кВт·год`],
            ['Річна вартість', `${monthly.reduce((s,r)=>s+r.total_cost_uah,0).toLocaleString('uk-UA',{maximumFractionDigits:0})} грн`],
            ['Денна зона', `${(monthly.reduce((s,r)=>s+(r.day_kwh||0),0)/monthly.reduce((s,r)=>s+r.total_kwh,0)*100).toFixed(1)}%`],
            ['Серед./місяць', `${(monthly.reduce((s,r)=>s+r.total_kwh,0)/monthly.length).toLocaleString('uk-UA',{maximumFractionDigits:0})} кВт·год`],
          ] as [string,string][]).map(([l,v])=>(
            <div key={l} className="bg-white rounded-lg p-3 border border-gray-100">
              <p className="text-gray-400 text-xs">{l}</p>
              <p className="font-semibold text-gray-900">{v}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
