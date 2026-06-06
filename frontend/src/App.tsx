// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Layout from './components/layout/Layout';
import Dashboard      from './pages/Dashboard';
import Consumption    from './pages/Consumption';
import ForecastPage   from './pages/ForecastPage';
import EmsPage        from './pages/EmsPage';
import EnergyBalance  from './pages/EnergyBalance';
import Analytics      from './pages/Analytics';
import Reports        from './pages/Reports';

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" />
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard"      element={<Dashboard />} />
          <Route path="consumption"    element={<Consumption />} />
          <Route path="forecast"       element={<ForecastPage />} />
          <Route path="ems"            element={<EmsPage />} />
          <Route path="energy-balance" element={<EnergyBalance />} />
          <Route path="analytics"      element={<Analytics />} />
          <Route path="reports"        element={<Reports />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
