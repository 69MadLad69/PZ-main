import { useState } from 'react';
import toast from 'react-hot-toast';
import api from '../services/api';
import { Card } from '../components/ui';

interface Section { id: string; label: string; description: string; lr: string; }

const SECTIONS: Section[] = [
  { id: 'dashboard',    label: 'Dashboard KPI', description: 'Місячне споживання, вартість', lr: 'ЛР1' },
  { id: 'consumption',  label: 'Споживання', description: 'Місячна/добова аналітика + тарифні зони', lr: 'ЛР1' },
  { id: 'forecast',     label: 'Прогноз споживання', description: 'Погодинний прогноз листопада (GB)', lr: 'ЛР2' },
  { id: 'model_metrics',label: 'Тестові передбачення ЛР2',description: 'Факт vs прогноз, метрики R²/RMSE/MAPE', lr: 'ЛР2' },
  { id: 'ems_energy',   label: 'EMS симуляція', description: 'Погодинні результати 168 кроків', lr: 'ЛР3' },
  { id: 'ems_economic', label: 'EMS економіка', description: 'CAPEX, NPV, IRR, Payback, прогони', lr: 'ЛР3' },
  { id: 'energy_flow',  label: 'Енергетичний баланс', description: 'Потоки СЕС→BESS→Навантаження', lr: 'ЛР3' },
];

const LR_COLORS: Record<string,string> = {
  'ЛР1':'bg-blue-100 text-blue-700',
  'ЛР2':'bg-purple-100 text-purple-700',
  'ЛР3':'bg-green-100 text-green-700',
};

export default function Reports() {
  const [selected, setSelected] = useState<Set<string>>(new Set(SECTIONS.map(s=>s.id)));
  const [period,   setPeriod]   = useState({ start:'2025-01-01', end:'2025-12-31' });
  const [format,   setFormat]   = useState('zip');
  const [loading,  setLoading]  = useState(false);
  const [preview,  setPreview]  = useState<string|null>(null);

  const toggle = (id:string) => {
    const n = new Set(selected); n.has(id)?n.delete(id):n.add(id); setSelected(n);
  };
  const selectAll = (g?:string) => {
    if (!g) { setSelected(new Set(SECTIONS.map(s=>s.id))); return; }
    const n = new Set(selected); SECTIONS.filter(s=>s.lr===g).forEach(s=>n.add(s.id)); setSelected(n);
  };
  const clearAll = () => setSelected(new Set());

  const params = () => new URLSearchParams({
    start: period.start, end: period.end,
    sections: [...selected].join(','),
  }).toString();

  const handlePreview = async () => {
    if (selected.size === 0) { toast.error('Оберіть розділи'); return; }
    setLoading(true);
    try {
      const gen = await api.post('/reports/generate', {
        start_date: period.start, end_date: period.end,
        sections: [...selected], format,
      });
      const rid = gen.data.report_id;
      const res = await api.get(`/reports/${rid}/preview?${params()}`, { responseType: 'text' });
      setPreview(typeof res.data === 'string' ? res.data : JSON.stringify(res.data, null, 2));
    } catch (err:any) {
      toast.error(err.response?.data?.detail ?? 'Помилка перегляду');
    } finally { setLoading(false); }
  };

  const handleDownload = async () => {
    if (selected.size === 0) { toast.error('Оберіть хоча б один розділ'); return; }
    setLoading(true);
    try {
      const gen = await api.post('/reports/generate', {
        start_date: period.start, end_date: period.end,
        sections: [...selected], format,
      });
      const rid = gen.data.report_id;
      const ext = format === 'excel' ? 'xlsx' : 'zip';
      const url = `/api/v1/reports/${rid}/download?${params()}&fmt=${format}`;
      const a = document.createElement('a');
      a.href = url;
      a.download = `ems_report_${period.start}_${period.end}.${ext}`;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      toast.success(`Завантаження ${ext.toUpperCase()}...`);
    } catch (err:any) {
      toast.error(err.response?.data?.detail ?? 'Помилка');
    } finally { setLoading(false); }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Генерація звіту</h2>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card title="Оберіть розділи (чекбокси)">
            <div className="flex flex-wrap gap-2 mb-4">
              <button onClick={()=>selectAll()} className="px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs rounded-lg">Всі</button>
              <button onClick={clearAll} className="px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs rounded-lg">Жодного</button>
              {['ЛР1','ЛР2','ЛР3'].map(lr=>(
                <button key={lr} onClick={()=>selectAll(lr)} className={`px-3 py-1 text-xs rounded-lg ${LR_COLORS[lr]}`}>Тільки {lr}</button>
              ))}
            </div>
            <div className="space-y-2">
              {SECTIONS.map(sec=>(
                <label key={sec.id}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    selected.has(sec.id)?'border-blue-300 bg-blue-50':'border-gray-200 hover:bg-gray-50'
                  }`}>
                  <input type="checkbox" checked={selected.has(sec.id)} onChange={()=>toggle(sec.id)}
                    className="mt-0.5 w-4 h-4 accent-blue-600"/>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-gray-900">{sec.label}</span>
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${LR_COLORS[sec.lr]}`}>{sec.lr}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{sec.description}</p>
                  </div>
                </label>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-3">Обрано: {selected.size}/{SECTIONS.length}</p>
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Параметри">
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Початок</label>
                <input type="date" value={period.start} onChange={e=>setPeriod(p=>({...p,start:e.target.value}))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"/>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Кінець</label>
                <input type="date" value={period.end} onChange={e=>setPeriod(p=>({...p,end:e.target.value}))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"/>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Формат</label>
                <div className="grid grid-cols-2 gap-2">
                  {[['zip','ZIP','CSV + summary'],['excel','Excel','.xlsx аркуші']].map(([v,l,d])=>(
                    <label key={v} className={`flex flex-col p-2 rounded-lg border cursor-pointer text-center ${
                      format===v?'border-blue-400 bg-blue-50':'border-gray-200 hover:bg-gray-50'}`}>
                      <input type="radio" name="fmt" value={v} checked={format===v} onChange={()=>setFormat(v)} className="sr-only"/>
                      <span className="font-semibold text-sm">{l}</span>
                      <span className="text-xs text-gray-400">{d}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </Card>
          <div className="space-y-2">
            <button onClick={handlePreview} disabled={loading||selected.size===0}
              className="w-full px-4 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium rounded-lg disabled:opacity-50 border border-gray-200">
              👁 Попередній перегляд
            </button>
            <button onClick={handleDownload} disabled={loading||selected.size===0}
              className="w-full px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg disabled:opacity-50">
              {loading?'⏳ Формування...':`⬇️ Завантажити ${format==='excel'?'XLSX':'ZIP'}`}
            </button>
          </div>
          <Card title="Що у архіві">
            <div className="text-xs text-gray-600 space-y-1">
              <p>ZIP з CSV для кожного розділу</p>
              <p>lr1_*.csv — споживання, тарифи</p>
              <p>lr2_*.csv — прогноз + тестові передбачення</p>
              <p>lr3_*.csv — EMS симуляція + прогони</p>
              <p>summary.txt — підсумок усіх KPI</p>
            </div>
          </Card>
        </div>
      </div>

      {preview && (
        <Card title="Попередній перегляд summary.txt">
          <pre className="text-xs bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap max-h-80 overflow-y-auto font-mono">
{preview}
          </pre>
          <button onClick={()=>setPreview(null)} className="mt-2 text-xs text-gray-400 hover:text-gray-600">Закрити</button>
        </Card>
      )}
    </div>
  );
}
