import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    } else if (err.response?.status >= 500) {
      console.error('Server error:', err.response?.data?.detail || err.message);
    }
    return Promise.reject(err);
  }
);

export default api;

// Auth
export const authApi = {
  login: (email: string, password: string) => api.post('/auth/login', { email, password }),
  register: (name: string, email: string, password: string) => api.post('/auth/register', { name, email, password }),
  me: () => api.get('/auth/me'),
  changePassword: (currentPassword: string, newPassword: string) => api.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword }),
};

// Market
export const marketApi = {
  overview: () => api.get('/market/overview'),
};

// Funds
export const fundsApi = {
  list: async (params?: any) => {
    const res = await api.get('/funds', { params });
    return { ...res, data: res.data.items || res.data, total: res.data.total };
  },
  detail: (code: string) => api.get(`/funds/${code}`),
  nav: (code: string, limit?: number) => api.get(`/funds/${code}/nav`, { params: { limit } }),
  holdings: (code: string) => api.get(`/funds/${code}/holdings`),
  valuations: (code: string, limit?: number) => api.get(`/funds/${code}/valuations`, { params: { limit } }),
  signals: (code: string, limit?: number) => api.get(`/funds/${code}/signals`, { params: { limit } }),
  // Batch lookup fund names by codes, returns Map<code, name>
  names: async (codes: string[]): Promise<Record<string, string>> => {
    const unique = [...new Set(codes.filter(Boolean))];
    if (unique.length === 0) return {};
    const res = await api.get('/funds', { params: { codes: unique.join(','), limit: 200 } });
    const items = res.data.items || res.data;
    const map: Record<string, string> = {};
    for (const f of items) {
      map[f.code] = f.name;
    }
    return map;
  },
};

// Signals
export const signalsApi = {
  list: async (params?: any) => {
    const res = await api.get('/signals', { params });
    return { ...res, data: res.data.items || res.data, total: res.data.total };
  },
  distribution: () => api.get('/signals/distribution'),
};

// Execution List
export const executionApi = {
  list: async (params?: any) => {
    const res = await api.get('/execution-list', { params });
    return { ...res, data: res.data.items || res.data, total: res.data.total };
  },
  create: (data: any) => api.post('/execution-list', data),
  update: (id: number, data: any) => api.put(`/execution-list/${id}`, data),
  updateBatch: (ids: number[], data: any) => api.put('/execution-list/batch/status', null, { params: { ids: ids.join(','), status: data.status } }),
  delete: (id: number) => api.delete(`/execution-list/${id}`),
  submit: () => api.post('/manual/submit-execution'),
  generateFromSignals: (action?: string) => api.post('/execution-list/generate-from-signals', null, { params: { action } }),
};

// Auto Mode
export const autoApi = {
  getConfig: () => api.get('/auto/config'),
  saveConfig: (totalAmount?: number, dailyAmount?: number, planType?: string) =>
    api.post('/auto/config', null, { params: { total_amount: totalAmount, daily_amount: dailyAmount, plan_type: planType } }),
  execute: () => api.post('/auto/execute'),
  getPortfolio: () => api.get('/auto/portfolio'),
  getReports: (params?: any) => api.get('/auto/reports', { params }),
  updateMarketValue: () => api.post('/auto/update-market-value'),
  getProfitDetail: () => api.get('/auto/profit-detail'),
};

// Manual Mode
export const manualApi = {
  listPortfolios: () => api.get('/manual/portfolios'),
  getPortfolio: (id: number) => api.get(`/manual/portfolios/${id}`),
  getPortfolioSummary: () => api.get('/manual/portfolio-summary'),
};

// Admin
export const adminApi = {
  syncFunds: () => api.post('/admin/sync/funds'),
  syncNav: () => api.post('/admin/sync/nav'),
  syncNavFull: () => api.post('/admin/sync/nav-full'),
  generateSignals: () => api.post('/admin/signals/generate'),
  backtest: (startDate: string, endDate: string, name?: string, params?: any) =>
    api.post('/admin/backtest', { start_date: startDate, end_date: endDate, name, params }),
  backtestResults: (skip?: number, limit?: number) =>
    api.get('/admin/backtest/results', { params: { skip, limit } }),
  backtestResult: (id: number) =>
    api.get(`/admin/backtest/results/${id}`),
  deleteBacktestResult: (id: number) =>
    api.delete(`/admin/backtest/results/${id}`),
  gridScan: (data: { start_date: string; end_date: string }) =>
    api.post('/admin/backtest/grid', data),
};

// Watchlist
export const watchlistApi = {
  list: (params?: any) => api.get('/watchlist', { params }),
  add: (fundCode: string, groupName?: string) => api.post('/watchlist', null, { params: { fund_code: fundCode, group_name: groupName || '默认' } }),
  remove: (id: number) => api.delete(`/watchlist/${id}`),
};

// Tools
export const toolsApi = {
  resetAuto: () => api.post('/tools/reset/auto'),
  resetManual: () => api.post('/tools/reset/manual'),
  resetSignals: () => api.post('/tools/reset/signals'),
};
