// frontend/src/services/api.ts  — updated with getTestPredictions
import axios from 'axios';

const api = axios.create({ baseURL: '/api/v1', timeout: 60000 });

api.interceptors.response.use(
  r => r,
  err => {
    console.error('API error:', err.response?.data || err.message);
    return Promise.reject(err);
  }
);

export const dashboardApi = {
  getSummary: (year = 2025) => api.get('/dashboard/summary', { params: { year } }),
  getKpi: (year = 2025) => api.get('/dashboard/kpi', { params: { year } }),
};

export const consumptionApi = {
  getMonthly: (year = 2025) => api.get('/consumption/monthly',  { params: { year } }),
  getDaily: (start: string, end: string)  => api.get('/consumption/daily', { params: { start, end } }),
  getHourly: (start: string, end: string, meter_id = 1, page = 1) =>
    api.get('/consumption/hourly', { params: { start, end, meter_id, page, page_size: 200 } }),
  getTariff: (start: string, end: string)  => api.get('/consumption/tariff',   { params: { start, end } }),
  getSpecific: (start: string, end: string)  => api.get('/consumption/specific', { params: { start, end } }),
};

export const forecastApi = {
  getSummary: () => api.get('/forecast/summary'),
  getHourly: (hours = 168) => api.get('/forecast/hourly', { params: { hours } }),
  getMetrics: () => api.get('/forecast/metrics'),
  getTestPredictions: (n = 168) => api.get('/forecast/test-predictions', { params: { n } }),
};

export const emsApi = {
  getStatus: () => api.get('/ems/status'),
  getSimulation: (run_id?: string) => api.get('/ems/simulation', { params: { run_id } }),
  getMetrics: (run_id?: string) => api.get('/ems/metrics',    { params: { run_id } }),
  getEconomics:  (run_id?: string) => api.get('/ems/economics',  { params: { run_id } }),
  getEnergyFlow: (run_id?: string) => api.get('/ems/energy-flow',{ params: { run_id } }),
  runSimulation: (start_date?: string, days = 7) =>
    api.post('/ems/run', null, { params: { start_date, days, strategy: 'tariff_optimized' } }),
};

export const weatherApi = {
  get: (start: string, end: string) => api.get('/weather', { params: { start, end } }),
};

export const reportsApi = {
  generate: (body: object) => api.post('/reports/generate', body),
};

export default api;
