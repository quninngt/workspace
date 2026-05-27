import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fundsApi, watchlistApi } from '../api/client';
import { ArrowLeft, Star, TrendingUp, TrendingDown, Minus, Shield, AlertTriangle } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

const LEVEL_COLORS: Record<string, string> = {
  S: 'text-green-600 bg-green-50 border-green-200',
  A: 'text-blue-600 bg-blue-50 border-blue-200',
  B: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  C: 'text-orange-600 bg-orange-50 border-orange-200',
  D: 'text-red-600 bg-red-50 border-red-200',
};

const ACTION_ICONS: Record<string, any> = {
  buy: TrendingUp, sell: TrendingDown, hold: Minus,
};

const ACTION_LABELS: Record<string, string> = {
  buy: '买入', sell: '卖出', hold: '持有',
};

const FUND_TYPES: Record<string, string> = {
  stock: '股票型', mixed: '混合型', bond: '债券型', index: '指数型',
  fof: 'FOF', money_market: '货币型', qdii: 'QDII',
};

export default function FundDetail() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [fund, setFund] = useState<any>(null);
  const [navData, setNavData] = useState<any[]>([]);
  const [valuations, setValuations] = useState<any[]>([]);
  const [holdings, setHoldings] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [riskMetrics, setRiskMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [holdingDate, setHoldingDate] = useState('');
  const [toast, setToast] = useState('');

  useEffect(() => {
    if (!code) return;
    const safeFetch = async (fn: () => Promise<any>) => {
      try { return await fn(); } catch { return { data: [] }; }
    };
    Promise.all([
      fundsApi.detail(code),
      safeFetch(() => fundsApi.nav(code, 120)),
      safeFetch(() => fundsApi.valuations(code, 60)),
      safeFetch(() => fundsApi.holdings(code)),
      safeFetch(() => fundsApi.signals(code, 20)),
      safeFetch(() => fundsApi.risk(code)),
    ]).then(([f, n, v, h, s, r]) => {
      setFund(f.data);
      setNavData([...n.data].reverse());
      setValuations([...v.data].reverse());
      const hData = h.data;
      setHoldings(hData);
      if (hData.length > 0) setHoldingDate(hData[0].date);
      setSignals(s.data);
      setRiskMetrics(r.data);
    }).finally(() => setLoading(false));
  }, [code]);

  const addWatchlist = async () => {
    if (!code) return;
    try {
      await watchlistApi.add(code);
      setToast('已添加到自选');
      setTimeout(() => setToast(''), 3000);
    } catch {
      setToast('添加失败');
      setTimeout(() => setToast(''), 3000);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" /></div>;
  if (!fund) return <p className="text-gray-400 text-center py-12">基金不存在</p>;

  return (
    <div>
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 px-4 py-2 bg-gray-800 text-white rounded-lg shadow-lg text-sm animate-fade-in">
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex items-start gap-3 mb-6">
        <button onClick={() => navigate(-1)} className="p-2 hover:bg-gray-100 rounded-lg transition-colors shrink-0"><ArrowLeft size={20} className="text-gray-500" /></button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-800 truncate">{fund.name}</h1>
            <span className="text-xs sm:text-sm font-mono text-gray-400 shrink-0">{fund.code}</span>
            <button onClick={addWatchlist} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors" title="加入自选">
              <Star size={18} className="text-gray-400 hover:text-yellow-500" />
            </button>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {FUND_TYPES[fund.type] || fund.type}
            {fund.company && ` · ${fund.company}`}
            {fund.fund_size && ` · ${(fund.fund_size / 1e8).toFixed(2)}亿`}
            {fund.risk_level && ` · ${fund.risk_level === 'low' ? '低风险' : fund.risk_level === 'medium' ? '中风险' : '高风险'}`}
          </p>
        </div>
        {/* Latest Signal Badge (desktop) */}
        {signals.length > 0 && (
          <div className={`hidden sm:block px-4 py-2 rounded-lg border shrink-0 ${LEVEL_COLORS[signals[0].level] || ''}`}>
            <div className="flex items-center justify-between mb-1">
              <div className="text-center">
                <p className="text-lg font-bold">{signals[0].level}</p>
                <p className="text-xs">{ACTION_LABELS[signals[0].action] || signals[0].action}</p>
                <p className="text-xs opacity-60">{signals[0].score.toFixed(1)}分</p>
              </div>
              {signals[0].recommendation?.short && (
                <div className="flex-1 ml-3 text-left">
                  <p className="text-xs font-medium">推荐理由</p>
                  <p className="text-xs opacity-80 leading-tight" title={signals[0].recommendation.professional}>
                    {signals[0].recommendation.short}
                  </p>
                  {signals[0].recommendation.plain && (
                    <details className="mt-1">
                      <summary className="text-xs opacity-60 cursor-pointer hover:opacity-100">通俗解释</summary>
                      <p className="text-xs mt-1 opacity-75 leading-relaxed whitespace-pre-line">
                        {signals[0].recommendation.plain}
                      </p>
                    </details>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Latest Signal Badge (mobile) */}
        {signals.length > 0 && (
          <div className={`sm:hidden w-full -mt-3 mb-3 px-4 py-2 rounded-lg border ${LEVEL_COLORS[signals[0].level] || ''}`}>
            <div className="flex items-center gap-3">
              <div className="text-center">
                <p className="text-lg font-bold">{signals[0].level}</p>
                <p className="text-xs">{ACTION_LABELS[signals[0].action] || signals[0].action}</p>
                <p className="text-xs opacity-60">{signals[0].score.toFixed(1)}分</p>
              </div>
              {signals[0].recommendation?.short && (
                <div className="flex-1 text-left min-w-0">
                  <p className="text-xs font-medium">推荐理由</p>
                  <p className="text-xs opacity-80 leading-tight truncate" title={signals[0].recommendation.professional}>
                    {signals[0].recommendation.short}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* NAV Chart */}
        <div className="lg:col-span-2 card">
          <h2 className="text-lg font-semibold mb-4">净值走势</h2>
          {navData.length === 0 ? (
            <p className="text-gray-400 text-center py-12">暂无净值数据</p>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={navData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="acc_nav" stroke="#2563eb" strokeWidth={2} dot={false} name="累计净值" />
                <Line type="monotone" dataKey="nav" stroke="#93c5fd" strokeWidth={1.5} dot={false} name="单位净值" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Signal History + Valuation */}
        <div className="space-y-6">
          {/* Signal History */}
          <div className="card">
            <h2 className="text-lg font-semibold mb-4">信号历史</h2>
            {signals.length === 0 ? (
              <p className="text-gray-400 text-center py-8">暂无信号</p>
            ) : (
              <div className="space-y-2">
                {signals.slice(0, 6).map(s => {
                  const ActionIcon = ACTION_ICONS[s.action] || Minus;
                  return (
                    <div key={s.id} className={`border rounded-lg px-3 py-2 ${LEVEL_COLORS[s.level] || ''}`}>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <ActionIcon size={14} />
                          <span className="font-bold text-sm">{s.level}</span>
                          <span className="text-xs opacity-75">{ACTION_LABELS[s.action] || s.action}</span>
                        </div>
                        <span className="text-xs">{s.date}</span>
                      </div>
                      <div className="mt-1 text-xs opacity-60">评分 {s.score.toFixed(1)}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Risk Metrics */}
          {riskMetrics && (
            <div className="card">
              <div className="flex items-center gap-2 mb-4">
                <Shield size={18} className={
                  riskMetrics.risk_level === 'low' ? 'text-green-600' :
                  riskMetrics.risk_level === 'high' ? 'text-red-600' : 'text-yellow-600'
                } />
                <h2 className="text-lg font-semibold">风险画像</h2>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  riskMetrics.risk_level === 'low' ? 'bg-green-100 text-green-700' :
                  riskMetrics.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                  'bg-yellow-100 text-yellow-700'
                }`}>
                  {riskMetrics.risk_level === 'low' ? '低风险' :
                   riskMetrics.risk_level === 'high' ? '高风险' : '中风险'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">年化波动率</p>
                  <p className="text-lg font-bold text-gray-800">{(riskMetrics.volatility * 100).toFixed(1)}%</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">95% VaR</p>
                  <p className="text-lg font-bold text-gray-800">{(riskMetrics.var_95 * 100).toFixed(2)}%</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">夏普比率</p>
                  <p className="text-lg font-bold text-gray-800">{riskMetrics.sharpe_ratio ?? '--'}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">最大回撤</p>
                  <p className="text-lg font-bold text-red-600">{(riskMetrics.max_drawdown * 100).toFixed(1)}%</p>
                  {riskMetrics.max_drawdown_days && (
                    <p className="text-xs text-gray-400 mt-0.5">恢复 {riskMetrics.max_drawdown_days} 天</p>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 sm:gap-4 mt-3 pt-3 border-t text-xs text-gray-500">
                <span>累计收益: <strong className={riskMetrics.total_return >= 0 ? 'text-green-600' : 'text-red-600'}>{(riskMetrics.total_return * 100).toFixed(1)}%</strong></span>
                <span>年化收益: <strong className={riskMetrics.annualized_return >= 0 ? 'text-green-600' : 'text-red-600'}>{(riskMetrics.annualized_return * 100).toFixed(1)}%</strong></span>
                <span>数据天数: {riskMetrics.trading_days}</span>
              </div>
            </div>
          )}

          {/* PE/PB Valuation */}
          <div className="card">
            <h2 className="text-lg font-semibold mb-4">估值分析</h2>
            {valuations.length === 0 ? (
              <p className="text-gray-400 text-center py-8">暂无估值数据</p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={valuations}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="pe_percentile" stroke="#f59e0b" fill="#fef3c7" strokeWidth={2} name="PE百分位" />
                  <Area type="monotone" dataKey="pb_percentile" stroke="#8b5cf6" fill="#f3e8ff" strokeWidth={2} name="PB百分位" />
                </AreaChart>
              </ResponsiveContainer>
            )}
            {/* Legend */}
            <div className="flex flex-wrap items-center gap-2 sm:gap-4 mt-3 text-xs text-gray-500">
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-500 inline-block" /> PE百分位</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-purple-500 inline-block" /> PB百分位</span>
              <span className="text-gray-300">|</span>
              <span className="text-green-600">≤20% 低估</span>
              <span className="text-red-600">≥80% 高估</span>
            </div>
          </div>
        </div>
      </div>

      {/* Holdings Table */}
      <div className="card mt-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">持仓股票</h2>
          {holdingDate && <span className="text-xs text-gray-400">报告期: {holdingDate}</span>}
        </div>
        {holdings.length === 0 ? (
          <p className="text-gray-400 text-center py-8">暂无持仓数据</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr className="border-b text-left text-sm text-gray-500">
                  <th className="px-4 py-3 font-medium">#</th>
                  <th className="px-4 py-3 font-medium">股票代码</th>
                <th className="px-4 py-3 font-medium">股票名称</th>
                <th className="px-4 py-3 font-medium">占比(%)</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="px-4 py-3 text-sm text-gray-400">{i + 1}</td>
                  <td className="px-4 py-3 text-sm font-mono text-gray-500">{h.stock_code || '--'}</td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-800">{h.stock_name}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    <div className="flex items-center gap-2">
                      <div className="w-24 bg-gray-100 rounded-full h-1.5">
                        <div className="bg-primary-500 h-1.5 rounded-full" style={{ width: `${Math.min(h.ratio || 0, 100)}%` }} />
                      </div>
                      <span>{h.ratio?.toFixed(2) || '--'}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}
