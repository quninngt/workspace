import { useState, useEffect } from 'react';
import { adminApi } from '../api/client';
import {
  BarChart3, TrendingUp, TrendingDown, Activity, AlertCircle,
  Trash2, ChevronDown, ChevronUp, History, Grid3X3, ArrowUpDown,
  Award, RefreshCw, Eye, Weight, Zap, Shield
} from 'lucide-react';

interface BacktestParams {
  initial_capital: number;
  factor_weights: Record<string, number>;
  buy_weights: Record<string, number>;
  sell_ratios: Record<string, number>;
  max_single_fund_ratio: number;
  max_daily_buys: number;
  normalize_signals: boolean;
}

interface HistoryItem {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  performance: Record<string, number>;
  created_at: string;
}

interface GridResult {
  rank: number;
  composite_score: number;
  label: string;
  weights: Record<string, number>;
  performance: {
    total_return_pct: number;
    benchmark_return_pct: number;
    excess_return_pct: number;
    max_drawdown_pct: number;
    sharpe_ratio: number;
    information_ratio: number;
    profit_loss_ratio: number;
    win_rate_pct: number;
    annualized_return_pct: number;
    total_trading_cost: number;
    buy_cost: number;
    sell_cost: number;
  };
  signal_distribution: Record<string, number>;
  factor_contributions: Record<string, number>;
}

const DEFAULT_PARAMS: BacktestParams = {
  initial_capital: 1_000_000,
  factor_weights: { valuation: 0.15, trend: 0.10, momentum: 0.30, quality: 0.30, sentiment: 0.15 },
  buy_weights: { S: 2.0, A: 1.0 },
  sell_ratios: { C: 0.25, D: 0.50 },
  max_single_fund_ratio: 0.30,
  max_daily_buys: 5,
  normalize_signals: false,
};

const FACTOR_LABELS: Record<string, string> = {
  valuation: '估值', trend: '趋势', momentum: '动量', quality: '质量', sentiment: '情绪',
};
const FACTOR_COLORS: Record<string, string> = {
  valuation: 'text-purple-600 bg-purple-50',
  trend: 'text-blue-600 bg-blue-50',
  momentum: 'text-green-600 bg-green-50',
  quality: 'text-orange-600 bg-orange-50',
  sentiment: 'text-pink-600 bg-pink-50',
};
const FACTOR_BAR_COLORS: Record<string, string> = {
  valuation: 'bg-purple-500', trend: 'bg-blue-500', momentum: 'bg-green-500',
  quality: 'bg-orange-500', sentiment: 'bg-pink-500',
};
const FACTOR_ORDER = ['valuation', 'trend', 'momentum', 'quality', 'sentiment'];

export default function Backtest() {
  const [tab, setTab] = useState<'single' | 'grid'>('single');
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [backtestName, setBacktestName] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [params, setParams] = useState<BacktestParams>({ ...DEFAULT_PARAMS });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState('');

  // Grid scan state
  const [gridRunning, setGridRunning] = useState(false);
  const [gridResult, setGridResult] = useState<GridResult[] | null>(null);
  const [gridBest, setGridBest] = useState<any>(null);
  const [gridImprovement, setGridImprovement] = useState<any>(null);
  const [gridInfo, setGridInfo] = useState<any>(null);
  const [sortKey, setSortKey] = useState<string>('composite_score');
  const [sortAsc, setSortAsc] = useState(false);
  const [expandedWeights, setExpandedWeights] = useState<number | null>(null);

  useEffect(() => { loadHistory(); }, []);

  const loadHistory = async () => {
    try {
      const res = await adminApi.backtestResults(0, 50);
      setHistory(res.data.items || []);
    } catch { /* silent */ }
  };

  // ── Single backtest ──

  const handleRun = async () => {
    setRunning(true); setError(''); setResult(null);
    try {
      await adminApi.backtest(startDate, endDate, backtestName || undefined, params);
      let attempts = 0;
      const poll = async () => {
        try {
          const res = await adminApi.backtestResults(0, 1);
          const items = res.data.items || [];
          if (items.length > 0) {
            const detail = await adminApi.backtestResult(items[0].id);
            setResult(detail.data);
            setRunning(false);
            loadHistory();
            return;
          }
        } catch { /* ignore */ }
        attempts++;
        if (attempts < 120) setTimeout(poll, 3000);
        else { setError('回测超时，请稍后查看'); setRunning(false); }
      };
      setTimeout(poll, 5000);
    } catch (err: any) {
      setError(err.response?.data?.detail || '启动回测失败');
      setRunning(false);
    }
  };

  const loadResult = async (id: number) => {
    try {
      const res = await adminApi.backtestResult(id);
      setResult(res.data);
    } catch { setError('加载结果失败'); }
  };

  const deleteResult = async (id: number) => {
    try {
      await adminApi.deleteBacktestResult(id);
      setHistory(history.filter(h => h.id !== id));
      if (result?.id === id) setResult(null);
    } catch { setError('删除失败'); }
  };

  const updateFactorWeight = (key: string, value: number) => {
    setParams({ ...params, factor_weights: { ...params.factor_weights, [key]: value } });
  };

  // ── Grid scan ──

  const handleGridRun = async () => {
    setGridRunning(true); setGridResult(null); setGridBest(null); setError('');
    try {
      await adminApi.gridScan({ start_date: startDate, end_date: endDate });
      let attempts = 0;
      const poll = async () => {
        try {
          const res = await adminApi.backtestResults(0, 20);
          const items = res.data.items || [];
          const gridItem = items.find((i: any) => i.name?.startsWith('[网格]'));
          if (gridItem) {
            const detail = await adminApi.backtestResult(gridItem.id);
            const daily = detail.data.daily_values || [];
            setGridResult(daily);
            setGridInfo(detail.data.summary?.improvement || null);
            setGridBest(detail.data.summary || null);
            setGridRunning(false);
            loadHistory();
            return;
          }
        } catch { /* ignore */ }
        attempts++;
        if (attempts < 180) setTimeout(poll, 2000);
        else { setError('网格扫描超时，请稍后查看历史记录'); setGridRunning(false); }
      };
      setTimeout(poll, 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || '启动网格扫描失败');
      setGridRunning(false);
    }
  };

  const sortedGrid = gridResult ? [...gridResult].sort((a: any, b: any) => {
    const av = a.performance?.[sortKey] ?? a[sortKey] ?? 0;
    const bv = b.performance?.[sortKey] ?? b[sortKey] ?? 0;
    return sortAsc ? av - bv : bv - av;
  }) : [];

  const sortedKey = (key: string) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  const SortIcon = (key: string) => (
    sortKey === key
      ? <ArrowUpDown size={12} className={`inline ml-1 ${sortAsc ? 'rotate-180' : ''}`} />
      : <ArrowUpDown size={12} className="inline ml-1 opacity-30" />
  );

  const perf = result?.performance;
  const summary = result?.summary;
  const usedParams = result?.params_used;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800">历史回测</h1>
        <p className="text-gray-500 mt-1">基于历史信号模拟交易策略，修改参数迭代优化</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit">
        <button onClick={() => setTab('single')} className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${tab === 'single' ? 'bg-white shadow text-primary-600' : 'text-gray-500 hover:text-gray-700'}`}>
          <BarChart3 size={14} className="inline mr-1.5" />单次回测
        </button>
        <button onClick={() => setTab('grid')} className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${tab === 'grid' ? 'bg-white shadow text-primary-600' : 'text-gray-500 hover:text-gray-700'}`}>
          <Grid3X3 size={14} className="inline mr-1.5" />参数网格扫描
        </button>
      </div>

      {/* ────── Single Tab ────── */}
      {tab === 'single' && (
        <>
          {/* Controls */}
          <div className="card mb-6">
            <div className="flex items-end gap-4 flex-wrap">
              <div>
                <label className="text-sm text-gray-500 block mb-1">开始日期</label>
                <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="input-field" max={endDate} />
              </div>
              <div>
                <label className="text-sm text-gray-500 block mb-1">结束日期</label>
                <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="input-field" min={startDate} />
              </div>
              <div>
                <label className="text-sm text-gray-500 block mb-1">名称（可选）</label>
                <input type="text" value={backtestName} onChange={e => setBacktestName(e.target.value)} className="input-field" placeholder="如：默认参数" />
              </div>
              <button onClick={handleRun} disabled={running} className="btn-primary flex items-center gap-2">
                {running ? (
                  <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" /> 回测进行中...</>
                ) : (
                  <><BarChart3 size={16} /> 运行回测</>
                )}
              </button>
            </div>

            <button onClick={() => setShowAdvanced(!showAdvanced)} className="flex items-center gap-1 text-sm text-primary-600 mt-3 hover:text-primary-700">
              {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              高级参数
            </button>

            {showAdvanced && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">初始资金</label>
                    <input type="number" value={params.initial_capital} onChange={e => setParams({ ...params, initial_capital: Number(e.target.value) })} className="input-field" />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">每日最大买入</label>
                    <input type="number" value={params.max_daily_buys} onChange={e => setParams({ ...params, max_daily_buys: Number(e.target.value) })} className="input-field" min={1} />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">单基金上限比例</label>
                    <input type="number" value={params.max_single_fund_ratio} onChange={e => setParams({ ...params, max_single_fund_ratio: Number(e.target.value) })} className="input-field" step={0.05} min={0} max={1} />
                  </div>
                  <div className="flex items-end">
                    <label className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={params.normalize_signals} onChange={e => setParams({ ...params, normalize_signals: e.target.checked })} className="rounded" />信号归一化
                    </label>
                  </div>
                </div>

                <div>
                  <label className="text-xs text-gray-500 block mb-2">因子权重（总和 = 1.0）</label>
                  <div className="grid grid-cols-5 gap-2">
                    {Object.entries(FACTOR_LABELS).map(([key, label]) => (
                      <div key={key}>
                        <label className="text-xs text-gray-400 block mb-1">{label}</label>
                        <input type="number" step={0.05} min={0} max={1}
                          value={params.factor_weights[key] || 0}
                          onChange={e => updateFactorWeight(key, Number(e.target.value))}
                          className="input-field text-sm" />
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">S 买入权重</label>
                    <input type="number" step={0.5} value={params.buy_weights.S} onChange={e => setParams({ ...params, buy_weights: { ...params.buy_weights, S: Number(e.target.value) } })} className="input-field" />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">A 买入权重</label>
                    <input type="number" step={0.5} value={params.buy_weights.A} onChange={e => setParams({ ...params, buy_weights: { ...params.buy_weights, A: Number(e.target.value) } })} className="input-field" />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">C 卖出比例</label>
                    <input type="number" step={0.05} min={0} max={1} value={params.sell_ratios.C} onChange={e => setParams({ ...params, sell_ratios: { ...params.sell_ratios, C: Number(e.target.value) } })} className="input-field" />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">D 卖出比例</label>
                    <input type="number" step={0.05} min={0} max={1} value={params.sell_ratios.D} onChange={e => setParams({ ...params, sell_ratios: { ...params.sell_ratios, D: Number(e.target.value) } })} className="input-field" />
                  </div>
                </div>
              </div>
            )}

            {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
          </div>

          {running && !result && (
            <div className="card flex items-center justify-center h-48">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-3" />
                <p className="text-gray-500">回测运行中，请稍候...</p>
                <p className="text-gray-400 text-xs mt-1">通常需要 30-60 秒</p>
              </div>
            </div>
          )}

          {history.length > 0 && !running && (
            <div className="card mb-6">
              <div className="flex items-center gap-2 mb-3">
                <History size={16} className="text-gray-400" />
                <h3 className="text-sm font-semibold text-gray-700">历史记录</h3>
              </div>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {history.filter(h => !h.name?.startsWith('[网格]')).map(item => (
                  <div key={item.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50">
                    <button onClick={() => loadResult(item.id)} className="flex-1 text-left">
                      <span className="text-sm font-medium text-gray-700">{item.name || `${item.start_date}~${item.end_date}`}</span>
                      <span className="text-xs text-gray-400 ml-2">{item.created_at?.slice(0, 16)}</span>
                    </button>
                    <div className="flex items-center gap-3">
                      <span className={`text-sm font-mono ${(item.performance?.total_return_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {item.performance?.total_return_pct > 0 ? '+' : ''}{item.performance?.total_return_pct}%
                      </span>
                      <button onClick={() => deleteResult(item.id)} className="text-gray-300 hover:text-red-500"><Trash2 size={14} /></button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result && renderSingleResult(result, perf, summary, usedParams)}
        </>
      )}

      {/* ────── Grid Scan Tab ────── */}
      {tab === 'grid' && (
        <>
          <div className="card mb-6">
            <div className="flex items-end gap-4 flex-wrap">
              <div>
                <label className="text-sm text-gray-500 block mb-1">开始日期</label>
                <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="input-field" max={endDate} />
              </div>
              <div>
                <label className="text-sm text-gray-500 block mb-1">结束日期</label>
                <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="input-field" min={startDate} />
              </div>
              <button onClick={handleGridRun} disabled={gridRunning} className="btn-primary flex items-center gap-2">
                {gridRunning ? (
                  <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" /> 扫描中...</>
                ) : (
                  <><Grid3X3 size={16} /> 启动网格扫描</>
                )}
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-3">
              自动尝试 25+ 种因子权重组合，用 Sharpe 比率+收益率排序，找到最优参数配置
            </p>
            {error && tab === 'grid' && <p className="text-red-500 text-sm mt-2">{error}</p>}
          </div>

          {gridRunning && (
            <div className="card flex items-center justify-center h-48">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-3" />
                <p className="text-gray-500">网格扫描运行中...</p>
                <p className="text-gray-400 text-xs mt-1">正在尝试 ~30 种权重组合，可能需要 2-5 分钟</p>
              </div>
            </div>
          )}

          {gridResult && sortedGrid.length > 0 && (
            <>
              {/* Best result highlight */}
              {gridBest && renderBestCard(gridBest)}

              {/* Sort controls */}
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs text-gray-400">排序:</span>
                {['composite_score', 'sharpe_ratio', 'total_return_pct', 'max_drawdown_pct', 'annualized_return_pct', 'win_rate_pct'].map(k => (
                  <button key={k} onClick={() => sortedKey(k)}
                    className={`text-xs px-2 py-1 rounded ${sortKey === k ? 'bg-primary-50 text-primary-600 font-medium' : 'text-gray-400 hover:text-gray-600'}`}>
                    {k === 'composite_score' ? '综合评分' :
                     k === 'sharpe_ratio' ? 'Sharpe' :
                     k === 'total_return_pct' ? '总收益' :
                     k === 'max_drawdown_pct' ? '最大回撤' :
                     k === 'win_rate_pct' ? '胜率' : '年化收益'}
                    {SortIcon(k)}
                  </button>
                ))}
              </div>

              {/* Results table */}
              <div className="card overflow-hidden mb-6">
                <div className="table-wrap">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 border-b bg-gray-50">
                        <th className="py-2.5 px-3 font-medium w-10">#</th>
                        <th className="py-2.5 px-3 font-medium">策略标签</th>
                        <th className="py-2.5 px-3 font-medium">综合分</th>
                        <th className="py-2.5 px-3 font-medium">Sharpe</th>
                        <th className="py-2.5 px-3 font-medium">总收益</th>
                        <th className="py-2.5 px-3 font-medium">年化</th>
                        <th className="py-2.5 px-3 font-medium">最大回撤</th>
                        <th className="py-2.5 px-3 font-medium">胜率</th>
                        <th className="py-2.5 px-3 font-medium">基准</th>
                        <th className="py-2.5 px-3 font-medium w-16">权重</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedGrid.map((r: any, i: number) => {
                        const p = r.performance || {};
                        const isBest = i === 0;
                        const isDefault = r.label === '当前默认';
                        return (
                          <tr key={i} className={`border-b last:border-0 hover:bg-gray-50 ${isBest ? 'bg-green-50/50' : ''} ${isDefault ? 'bg-blue-50/30' : ''}`}>
                            <td className="py-2.5 px-3">
                              {isBest ? <Award size={16} className="text-yellow-500" /> : r.rank || i + 1}
                            </td>
                            <td className="py-2.5 px-3">
                              <span className="font-medium text-gray-700">{r.label}</span>
                              {isDefault && <span className="ml-1.5 text-xs text-blue-500">(默认)</span>}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-xs">{r.composite_score || '-'}</td>
                            <td className={`py-2.5 px-3 font-mono ${(p.sharpe_ratio || 0) > 0.5 ? 'text-green-600' : 'text-gray-600'}`}>
                              {p.sharpe_ratio?.toFixed(2) || '-'}
                            </td>
                            <td className={`py-2.5 px-3 font-mono font-semibold ${(p.total_return_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {p.total_return_pct != null ? `${p.total_return_pct > 0 ? '+' : ''}${p.total_return_pct.toFixed(1)}%` : '-'}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-xs text-gray-600">
                              {p.annualized_return_pct != null ? `${p.annualized_return_pct > 0 ? '+' : ''}${p.annualized_return_pct.toFixed(1)}%` : '-'}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-red-600">
                              -{p.max_drawdown_pct?.toFixed(1) || '-'}%
                            </td>
                            <td className="py-2.5 px-3 font-mono text-xs text-gray-600">
                              {p.win_rate_pct?.toFixed(0) || '-'}%
                            </td>
                            <td className="py-2.5 px-3 font-mono text-xs text-gray-500">
                              {p.benchmark_return_pct != null ? `${p.benchmark_return_pct > 0 ? '+' : ''}${p.benchmark_return_pct.toFixed(1)}%` : '-'}
                            </td>
                            <td className="py-2.5 px-3">
                              <button onClick={() => setExpandedWeights(expandedWeights === i ? null : i)}
                                className="text-gray-400 hover:text-gray-600">
                                <Weight size={14} />
                              </button>
                              {expandedWeights === i && (
                                <div className="absolute z-10 mt-1 p-2 bg-white shadow-lg rounded-lg border text-xs space-y-1 min-w-[140px]">
                                  {FACTOR_ORDER.map(f => (
                                    <div key={f} className="flex justify-between gap-3">
                                      <span className="text-gray-500">{FACTOR_LABELS[f]}</span>
                                      <span className={`font-mono font-medium ${FACTOR_COLORS[f].split(' ')[0]}`}>
                                        {(r.weights?.[f] * 100).toFixed(1)}%
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Factor weight distribution chart for top N */}
              {renderWeightComparison(sortedGrid.slice(0, 10))}

              {/* Factor contribution analysis for top 3 */}
              {renderFactorContributionComparison(sortedGrid.slice(0, 3))}
            </>
          )}

          {/* Grid history */}
          {history.filter(h => h.name?.startsWith('[网格]')).length > 0 && !gridRunning && (
            <div className="card">
              <div className="flex items-center gap-2 mb-3">
                <History size={16} className="text-gray-400" />
                <h3 className="text-sm font-semibold text-gray-700">网格扫描历史</h3>
              </div>
              <div className="space-y-1 max-h-36 overflow-y-auto">
                {history.filter(h => h.name?.startsWith('[网格]')).map(item => (
                  <div key={item.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50">
                    <span className="text-sm text-gray-600">{item.name} — {item.created_at?.slice(0, 16)}</span>
                    <div className="flex items-center gap-2">
                      {item.performance?.total_return_pct != null && (
                        <span className={`text-xs font-mono ${(item.performance?.total_return_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          Sharpe: {(item.performance?.sharpe_ratio || 0).toFixed(2)}
                        </span>
                      )}
                      <button onClick={() => loadFromHistory(item.id)} className="text-primary-500 hover:text-primary-600">
                        <Eye size={14} />
                      </button>
                      <button onClick={() => deleteResult(item.id)} className="text-gray-300 hover:text-red-500">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );

  function loadFromHistory(id: number) {
    adminApi.backtestResult(id).then(res => {
      const data = res.data;
      setGridResult(data.daily_values || []);
      setGridBest(data.summary || null);
      setGridImprovement(data.summary?.improvement || null);
      setGridInfo(data.summary?.improvement || null);
    }).catch(() => setError('加载网格结果失败'));
  }
}

// ── Shared render functions ──

function renderSingleResult(result: any, perf: any, summary: any, usedParams: any) {
  return (
    <>
      {usedParams && (
        <div className="card mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">回测参数</h3>
          <div className="flex flex-wrap gap-3 text-xs text-gray-500">
            <span>资金: ¥{usedParams.initial_capital?.toLocaleString()}</span>
            {Object.entries(usedParams.factor_weights || {}).map(([k, v]) => (
              <span key={k}>{FACTOR_LABELS[k] || k}: {(v as number * 100).toFixed(0)}%</span>
            ))}
            <span>S权重: {usedParams.buy_weights?.S}</span>
            <span>A权重: {usedParams.buy_weights?.A}</span>
            <span>单基金上限: {(usedParams.max_single_fund_ratio * 100).toFixed(0)}%</span>
            <span>每日最多买: {usedParams.max_daily_buys}</span>
            {usedParams.normalize_signals && <span className="text-primary-600">归一化: 开</span>}
          </div>
        </div>
      )}

      <div className="card mb-6">
        <h2 className="text-lg font-semibold mb-4">回测概要</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div><p className="text-sm text-gray-500">回测区间</p><p className="font-medium">{summary?.start_date} ~ {summary?.end_date}</p></div>
          <div><p className="text-sm text-gray-500">交易天数</p><p className="font-medium">{summary?.trading_days}</p></div>
          <div><p className="text-sm text-gray-500">基金数量</p><p className="font-medium">{summary?.funds_scored?.toLocaleString()}</p></div>
          <div><p className="text-sm text-gray-500">信号总数</p><p className="font-medium">{summary?.total_signals_generated?.toLocaleString()}</p></div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="card">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-green-50"><TrendingUp size={20} className="text-green-600" /></div>
            <span className="text-sm text-gray-500">策略收益</span>
          </div>
          <p className={`text-2xl font-bold ${(perf?.total_return_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {perf?.total_return_pct > 0 ? '+' : ''}{perf?.total_return_pct}%
          </p>
        </div>
        <div className="card">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-blue-50"><Activity size={20} className="text-blue-600" /></div>
            <span className="text-sm text-gray-500">基准收益</span>
          </div>
          <p className={`text-2xl font-bold ${(perf?.benchmark_return_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {perf?.benchmark_return_pct > 0 ? '+' : ''}{perf?.benchmark_return_pct}%
          </p>
          {perf?.excess_return_pct != null && (
            <p className={`text-xs mt-1 ${(perf.excess_return_pct || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              超额 {perf.excess_return_pct > 0 ? '+' : ''}{perf.excess_return_pct}%
            </p>
          )}
        </div>
        <div className="card">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-red-50"><TrendingDown size={20} className="text-red-600" /></div>
            <span className="text-sm text-gray-500">最大回撤</span>
          </div>
          <p className="text-2xl font-bold text-red-600">-{perf?.max_drawdown_pct}%</p>
        </div>
        <div className="card">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-purple-50"><BarChart3 size={20} className="text-purple-600" /></div>
            <span className="text-sm text-gray-500">Sharpe Ratio</span>
          </div>
          <p className="text-2xl font-bold text-gray-800">{perf?.sharpe_ratio}</p>
          <p className="text-xs text-gray-400 mt-1">胜率 {perf?.win_rate_pct}% | 年化 {perf?.annualized_return_pct}%</p>
        </div>
      </div>

      {/* Phase 3 新指标行 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="card bg-gray-50">
          <p className="text-xs text-gray-400 mb-1">信息比率</p>
          <p className="text-lg font-bold text-gray-800">{perf?.information_ratio ?? '-'}</p>
          <p className="text-[10px] text-gray-400 mt-1">超额收益 / 跟踪误差</p>
        </div>
        <div className="card bg-gray-50">
          <p className="text-xs text-gray-400 mb-1">盈亏比</p>
          <p className={`text-lg font-bold ${(perf?.profit_loss_ratio || 0) >= 1 ? 'text-green-600' : 'text-orange-600'}`}>
            {perf?.profit_loss_ratio ?? '-'}
          </p>
          <p className="text-[10px] text-gray-400 mt-1">平均盈利 / 平均亏损</p>
        </div>
        <div className="card bg-gray-50">
          <p className="text-xs text-gray-400 mb-1">总交易成本</p>
          <p className="text-lg font-bold text-gray-800">¥{(perf?.total_trading_cost || 0).toLocaleString()}</p>
          <p className="text-[10px] text-gray-400 mt-1">
            买 ¥{(perf?.buy_cost || 0).toLocaleString()} / 卖 ¥{(perf?.sell_cost || 0).toLocaleString()}
          </p>
        </div>
        <div className="card bg-gray-50">
          <p className="text-xs text-gray-400 mb-1">成本占比</p>
          <p className="text-lg font-bold text-gray-800">
            {perf?.total_trading_cost && perf?.total_return_pct
              ? `${((perf.total_trading_cost / 1000000) * 100).toFixed(2)}%`
              : '-'}
          </p>
          <p className="text-[10px] text-gray-400 mt-1">交易成本 / 初始资金</p>
        </div>
      </div>

      {result?.signal_distribution && Object.keys(result.signal_distribution).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">信号等级分布</h3>
            <div className="space-y-2">
              {['S', 'A', 'B', 'C', 'D'].map(level => {
                const count = result.signal_distribution[level] || 0;
                const total = Object.values(result.signal_distribution).reduce((a: number, b: any) => a + (b as number), 0) as number;
                const pct = total > 0 ? (count / total * 100) : 0;
                const colors: Record<string, string> = { S: 'bg-purple-500', A: 'bg-green-500', B: 'bg-blue-500', C: 'bg-yellow-500', D: 'bg-red-500' };
                return (
                  <div key={level} className="flex items-center gap-2">
                    <span className="w-6 text-xs font-bold text-gray-600">{level}</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                      <div className={`h-full rounded-full ${colors[level] || 'bg-gray-300'}`} style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs text-gray-500 w-20 text-right">{count.toLocaleString()} ({pct.toFixed(1)}%)</span>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">因子贡献度</h3>
            {result?.factor_contributions && Object.keys(result.factor_contributions).length > 0 ? (
              <div className="space-y-2">
                {[
                  { key: 'valuation', label: '估值', color: 'bg-purple-500' },
                  { key: 'trend', label: '趋势', color: 'bg-blue-500' },
                  { key: 'momentum', label: '动量', color: 'bg-green-500' },
                  { key: 'quality', label: '质量', color: 'bg-orange-500' },
                  { key: 'sentiment', label: '情绪', color: 'bg-pink-500' },
                ].map(f => {
                  const pct = result.factor_contributions[f.key] || 0;
                  return (
                    <div key={f.key} className="flex items-center gap-2">
                      <span className="w-12 text-xs text-gray-600">{f.label}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                        <div className={`h-full rounded-full ${f.color}`} style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-gray-500 w-14 text-right">{pct}%</span>
                    </div>
                  );
                })}
              </div>
            ) : <p className="text-gray-400 text-sm">无因子数据</p>}
          </div>
        </div>
      )}

      {result?.monthly_returns && result.monthly_returns.length > 0 && (
        <div className="card mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">月度收益</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
            {result.monthly_returns.map((mr: any) => (
              <div key={mr.month} className={`p-3 rounded-lg text-center ${mr.return_pct >= 0 ? 'bg-green-50' : 'bg-red-50'}`}>
                <p className="text-xs text-gray-500">{mr.month}</p>
                <p className={`text-lg font-bold ${mr.return_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {mr.return_pct > 0 ? '+' : ''}{mr.return_pct}%
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {perf?.total_return_pct === 0 && (
        <div className="card border border-yellow-200 bg-yellow-50 mb-6">
          <div className="flex items-start gap-3">
            <AlertCircle size={20} className="text-yellow-600 mt-0.5 shrink-0" />
            <div>
              <p className="font-medium text-yellow-800">回测说明</p>
              <p className="text-sm text-yellow-700 mt-1">当前回测区间内所有信号均为 B(持有)，无买入/卖出信号触发交易。可尝试调整高级参数中的因子权重或信号阈值来增加信号分散度。</p>
            </div>
          </div>
        </div>
      )}

      {result?.daily_values && result.daily_values.length > 0 && (
        <details className="card mt-4">
          <summary className="text-sm font-semibold text-gray-700 cursor-pointer">
            每日详情 ({result.daily_values.length} 天)
          </summary>
          <div className="mt-3 max-h-64 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-4">日期</th>
                  <th className="py-2 pr-4">组合价值</th>
                  <th className="py-2 pr-4">现金</th>
                  <th className="py-2 pr-4">持仓数</th>
                  <th className="py-2 pr-4">信号数</th>
                </tr>
              </thead>
              <tbody>
                {result.daily_values.map((dv: any) => (
                  <tr key={dv.date} className="border-b last:border-0">
                    <td className="py-2 pr-4 text-gray-600">{dv.date}</td>
                    <td className="py-2 pr-4 font-mono">¥{dv.portfolio_value?.toLocaleString()}</td>
                    <td className="py-2 pr-4">¥{dv.cash?.toLocaleString()}</td>
                    <td className="py-2 pr-4">{dv.positions}</td>
                    <td className="py-2 pr-4">{dv.signals}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </>
  );
}

function renderBestCard(gridBest: any) {
  const imp = gridBest?.improvement;
  return (
    <div className="card border border-yellow-200 bg-gradient-to-br from-yellow-50 to-amber-50 mb-6">
      <div className="flex items-start gap-3 mb-4">
        <Award size={24} className="text-yellow-500 shrink-0" />
        <div>
          <h3 className="font-bold text-gray-800">最优策略：{gridBest?.best_label || '未知'}</h3>
          {imp && (
            <div className="flex flex-wrap gap-3 mt-2 text-sm">
              {imp.sharpe_improvement != null && (
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${imp.sharpe_improvement > 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  Sharpe {imp.sharpe_improvement > 0 ? '+' : ''}{imp.sharpe_improvement.toFixed(2)}
                </span>
              )}
              {imp.return_improvement_pct != null && (
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${imp.return_improvement_pct > 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  收益 {imp.return_improvement_pct > 0 ? '+' : ''}{imp.return_improvement_pct.toFixed(1)}%
                </span>
              )}
              {imp.max_dd_reduction_pct != null && (
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${imp.max_dd_reduction_pct > 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  回撤 {imp.max_dd_reduction_pct > 0 ? '-' : '+'}{Math.abs(imp.max_dd_reduction_pct).toFixed(1)}%
                </span>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="text-xs text-gray-500">
        vs 默认参数{gridBest?.default_label ? ` (${gridBest.default_label})` : ''}
      </div>
    </div>
  );
}

function renderWeightComparison(top10: any[]) {
  if (top10.length < 2) return null;
  return (
    <div className="card mb-6">
      <div className="flex items-center gap-2 mb-4">
        <Weight size={16} className="text-gray-400" />
        <h3 className="text-sm font-semibold text-gray-700">Top 10 策略权重分布</h3>
      </div>
      <div className="overflow-x-auto">
        <div className="flex gap-4 min-w-[600px] pb-2">
          {top10.map((r: any, i: number) => (
            <div key={i} className="flex-1 min-w-[56px]">
              <p className="text-[10px] text-gray-400 text-center mb-1 truncate" title={r.label}>
                #{i + 1}
              </p>
              <div className="flex flex-col-reverse h-32 rounded-lg overflow-hidden border">
                {FACTOR_ORDER.map(f => {
                  const pct = (r.weights?.[f] || 0) * 100;
                  return pct > 0 ? (
                    <div key={f} className={FACTOR_BAR_COLORS[f]} style={{ flex: pct }}>
                      <span className="text-[8px] text-white block text-center leading-none py-0.5">
                        {pct >= 8 ? `${pct.toFixed(0)}%` : ''}
                      </span>
                    </div>
                  ) : null;
                })}
              </div>
              <p className="text-[10px] text-center mt-1 font-mono text-gray-500">
                {r.performance?.sharpe_ratio?.toFixed(2)}
              </p>
            </div>
          ))}
        </div>
      </div>
      {/* Legend */}
      <div className="flex gap-3 mt-3 flex-wrap">
        {FACTOR_ORDER.map(f => (
          <span key={f} className={`text-xs px-2 py-0.5 rounded ${FACTOR_COLORS[f]}`}>
            {FACTOR_LABELS[f]}
          </span>
        ))}
      </div>
    </div>
  );
}

function renderFactorContributionComparison(top3: any[]) {
  if (top3.length < 2) return null;
  return (
    <div className="card mb-6">
      <div className="flex items-center gap-2 mb-4">
        <Zap size={16} className="text-gray-400" />
        <h3 className="text-sm font-semibold text-gray-700">Top 3 策略详情对比</h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {top3.map((r: any, i: number) => {
          const fc = r.factor_contributions || {};
          return (
            <div key={i} className={`p-4 rounded-lg border ${i === 0 ? 'bg-yellow-50 border-yellow-200' : 'bg-gray-50'}`}>
              <p className="text-sm font-semibold text-gray-700 mb-1">
                #{i + 1} {r.label}
                {i === 0 && <Award size={14} className="inline ml-1 text-yellow-500" />}
              </p>
              <p className="text-xs text-gray-400 mb-3">
                Sharpe {r.performance?.sharpe_ratio?.toFixed(2)} | 
                收益 {r.performance?.total_return_pct?.toFixed(1)}%
              </p>
              <div className="space-y-1.5">
                {FACTOR_ORDER.filter(f => fc[f] != null).map(f => (
                  <div key={f} className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 w-10">{FACTOR_LABELS[f]}</span>
                    <div className="flex-1 bg-gray-200 rounded-full h-2.5 overflow-hidden">
                      <div className={`h-full rounded-full ${FACTOR_BAR_COLORS[f]}`} style={{ width: `${fc[f]}%` }} />
                    </div>
                    <span className="text-xs font-mono text-gray-500 w-10 text-right">{fc[f]}%</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
