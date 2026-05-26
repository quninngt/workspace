import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import FundList from './pages/FundList';
import FundDetail from './pages/FundDetail';
import AutoFollow from './pages/AutoFollow';
import ManualFollow from './pages/ManualFollow';
import ManualPortfolio from './pages/ManualPortfolio';
import Watchlist from './pages/Watchlist';
import Settings from './pages/Settings';
import Backtest from './pages/Backtest';
import Tools from './pages/Tools';
import SignalList from './pages/SignalList';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div></div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="funds" element={<FundList />} />
          <Route path="funds/:code" element={<FundDetail />} />
          <Route path="auto" element={<AutoFollow />} />
          <Route path="manual" element={<ManualFollow />} />
          <Route path="portfolio" element={<ManualPortfolio />} />
          <Route path="watchlist" element={<Watchlist />} />
          <Route path="tools" element={<Tools />} />
          <Route path="signals" element={<SignalList />} />
          <Route path="signals/:level" element={<SignalList />} />
          <Route path="settings" element={<Settings />} />
          <Route path="backtest" element={<Backtest />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
