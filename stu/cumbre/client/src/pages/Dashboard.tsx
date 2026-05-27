import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { marketApi, executionApi, autoApi, macroApi } from '../api/client';
import { TrendingUp, TrendingDown, BarChart3, Activity, ListTodo, Briefcase, Clock, AlertCircle, Shield, Sun, Cloud, CloudRain } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

const SIGNAL_COLORS: Record<string, string> = {
  S: '#22c55e', A: '#3b82f6', B: '#f59e0b', C: '#f97316', D: '#ef4444',
};
const SIGNAL_LABELS: Record<string, string> = {
  S: '强买入', A: '买入', B: '持有', C: '卖出', D: '强卖出',
};
const INDEX_NAMES: Record<string, string> = {
  'sh000001': '上证指数', 'sz399001': '深证成指', 'sh000300': '沪深300',
  'sh000905': '中证500', 'sh000688': '科创50', 'sz399006': '创业板指',
};

function getPercentileColor(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return 'bg-gray-100 text-gray-400';
  if (pct <= 20) return 'bg-green-100 text-green-700 border-green-200';
  if (pct <= 40) return 'bg-lime-100 text-lime-700 border-lime-200';
  if (pct <= 60) return 'bg-yellow-100 text-yellow-700 border-yellow-200';
  if (pct <= 80) return 'bg-orange-100 text-orange-700 border-orange-200';
  return 'bg-red-100 text-red-700 border-red-200';
}

function getPercentileLabel(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return '--';
  if (pct <= 20) return '低估';
  if (pct <= 40) return '偏低';
  if (pct <= 60) return '适中';
  if (pct <= 80) return '偏高';
  return '高估';
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [market, setMarket] = useState<any>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [autoPortfolio, setAutoPortfolio] = useState<any>(null);
  const [macroSignal, setMacroSignal] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      marketApi.overview(),
      executionApi.list({ status: 'pending' }).catch(() => ({ data: [] })),
      autoApi.getPortfolio().catch(() => ({ data: null })),
      macroApi.getSignal().catch(() => ({ data: null })),
    ]).then(([m, ex, ap, macro]) => {
      setMarket(m.data);
      setPendingCount(ex.data?.length || 0);
      setAutoPortfolio(ap.data);
      setMacroSignal(macro.data);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" /></div>;

  const dist = market?.signal_distribution || {};
  const pieData = Object.entries(dist).map(([k, v]) => ({ name: SIGNAL_LABELS[k] || k, value: v as number, level: k }));
  const totalSignals = pieData.reduce((s, i) => s + i.value, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">市场总览</h1>
        <p className="text-gray-500 mt-1">全市场公募基金信号概览</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-500">收录基金</span>
            <BarChart3 className="text-primary-500" size={20} />
          </div>
          <p className="text-2xl font-bold text-gray-800">{(market?.fund_count || 0).toLocaleString()}</p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-500">今日信号</span>
            <Activity className="text-blue-500" size={20} />
          </div>
          <p className="text-2xl font-bold text-gray-800">{totalSignals.toLocaleString()}</p>
          {market?.latest_signal_date && <p className="text-xs text-gray-400 mt-1">{market.latest_signal_date}</p>}
        </div>
        <div className="card cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate('/manual')}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-500">待执行</span>
            <ListTodo className="text-yellow-500" size={20} />
          </div>
          <p className="text-2xl font-bold text-yellow-600">{pendingCount}</p>
          <p className="text-xs text-gray-400 mt-1">点击查看执行清单</p>
        </div>
        <div className="card cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate('/auto')}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-500">自动组合</span>
            <Briefcase className="text-purple-500" size={20} />
          </div>
          {autoPortfolio ? (
            <>
              <p className="text-2xl font-bold text-gray-800">¥{autoPortfolio.market_value?.toLocaleString() || '0'}</p>
              <p className="text-xs text-gray-400 mt-1">投入 ¥{autoPortfolio.total_invested?.toLocaleString() || '0'}</p>
            </>
          ) : (
            <>
              <p className="text-2xl font-bold text-gray-400">--</p>
              <p className="text-xs text-gray-400 mt-1">尚未启动</p>
            </>
          )}
        </div>
      </div>

      {/* Macro Environment Indicator */}
      {macroSignal && (
        <div className={`card border-l-4 ${
          macroSignal.signal === 'risk_on' ? 'border-l-green-500 bg-green-50' :
          macroSignal.signal === 'risk_off' ? 'border-l-red-500 bg-red-50' :
          'border-l-yellow-500 bg-yellow-50'
        }`}>
          <div className="flex flex-col sm:flex-row items-start gap-3">
            <div className="flex items-center gap-3">
              {macroSignal.signal === 'risk_on' ? (
                <Sun className="text-green-600" size={28} />
              ) : macroSignal.signal === 'risk_off' ? (
                <CloudRain className="text-red-600" size={28} />
              ) : (
                <Cloud className="text-yellow-600" size={28} />
              )}
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-semibold text-gray-800">宏观环境</h3>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    macroSignal.signal === 'risk_on' ? 'bg-green-200 text-green-800' :
                    macroSignal.signal === 'risk_off' ? 'bg-red-200 text-red-800' :
                    'bg-yellow-200 text-yellow-800'
                  }`}>
                    {macroSignal.signal === 'risk_on' ? '积极' :
                     macroSignal.signal === 'risk_off' ? '防守' : '中性'}
                  </span>
                </div>
                <p className="text-sm text-gray-600 mt-1">{macroSignal.reasoning}</p>
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-4">
                <div>
                  <p className="text-xs text-gray-500">PE百分位</p>
                  <p className="text-lg font-bold text-gray-800">
                    {macroSignal.pe_percentile !== null ? `${macroSignal.pe_percentile.toFixed(1)}%` : '--'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">评分折扣</p>
                  <p className="text-lg font-bold text-gray-800">
                    ×{macroSignal.multiplier}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Market Thermometer + Signal Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-lg font-semibold">市场温度计</h2>
            <span className="text-xs text-gray-400">PE 历史百分位</span>
          </div>
          {(!market?.indices || market.indices.length === 0) ? (
            <p className="text-gray-400 text-center py-8">暂无指数数据</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {market.indices.map((idx: any) => {
                const pct = idx.pe_percentile;
                const colorClass = getPercentileColor(pct);
                return (
                  <div key={idx.code} className={`rounded-lg border p-3 text-center ${colorClass}`}>
                    <p className="text-xs font-medium opacity-80">{INDEX_NAMES[idx.code] || idx.name || idx.code}</p>
                    <p className="text-lg font-bold mt-1">{pct !== null && pct !== undefined ? pct.toFixed(1) : '--'}<span className="text-xs font-normal">%</span></p>
                    <p className="text-xs font-medium mt-0.5">{getPercentileLabel(pct)}</p>
                    <p className="text-xs opacity-60 mt-0.5">PE {idx.pe?.toFixed(1) || '--'}</p>
                  </div>
                );
              })}
            </div>
          )}
          <div className="flex items-center justify-between mt-4 pt-3 border-t text-xs text-gray-400">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-green-100 border border-green-200" /> 低估 ≤20%</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-yellow-100 border border-yellow-200" /> 适中 40-60%</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-red-100 border border-red-200" /> 高估 ≥80%</span>
          </div>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">信号分布</h2>
          {pieData.length === 0 ? (
            <p className="text-gray-400 text-center py-8">暂无信号数据</p>
          ) : (
            <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-6">
              <ResponsiveContainer width={180} height={180}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={40} outerRadius={80}>
                    {pieData.map((entry) => (
                      <Cell key={entry.level} fill={SIGNAL_COLORS[entry.level]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2">
                {pieData.map(entry => (
                  <div
                    key={entry.level}
                    className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-50 rounded-lg px-2 py-1 transition-colors"
                    onClick={() => navigate(`/signals/${entry.level}`)}
                  >
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: SIGNAL_COLORS[entry.level] }} />
                    <span className="text-gray-600 w-12">{entry.name}</span>
                    <span className="font-medium text-gray-800">{entry.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {market?.latest_signal_date && (
            <p className="text-xs text-gray-400 mt-3">最新信号日期: {market.latest_signal_date}</p>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <button onClick={() => navigate('/funds')} className="card text-left hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center group-hover:bg-primary-100 transition-colors">
              <BarChart3 size={20} className="text-primary-600" />
            </div>
            <div>
              <p className="font-medium text-gray-800">浏览基金</p>
              <p className="text-xs text-gray-400">全市场基金筛选</p>
            </div>
          </div>
        </button>
        <button onClick={() => navigate('/manual')} className="card text-left hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-yellow-50 flex items-center justify-center group-hover:bg-yellow-100 transition-colors">
              <ListTodo size={20} className="text-yellow-600" />
            </div>
            <div>
              <p className="font-medium text-gray-800">执行清单</p>
              <p className="text-xs text-gray-400">{pendingCount} 项待处理</p>
            </div>
          </div>
        </button>
        <button onClick={() => navigate('/watchlist')} className="card text-left hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center group-hover:bg-purple-100 transition-colors">
              <Activity size={20} className="text-purple-600" />
            </div>
            <div>
              <p className="font-medium text-gray-800">自选管理</p>
              <p className="text-xs text-gray-400">关注的基金</p>
            </div>
          </div>
        </button>
      </div>
    </div>
  );
}
