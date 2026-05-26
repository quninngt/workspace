import { useState, useEffect } from 'react';
import { adminApi } from '../api/client';
import { BarChart3, TrendingUp, TrendingDown, Activity, AlertCircle, Trash2, ChevronDown, ChevronUp, History } from 'lucide-react';

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

export default function Backtest() {
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [backtestName, setBacktestName] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [params, setParams] = useState<BacktestParams>({ ...DEFAULT_PARAMS });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const res = await adminApi.backtestResults(0, 50);
      setHistory(res.data.items || []);
    } catch {
      // silent
    }
  };

  const handleRun = async () => {
    setRunning(true);
    setError('');
    setResult(null);
    try {
      await adminApi.backtest(startDate, endDate, backtestName || undefined, params);
      // Poll history for new result
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
        if (attempts < 120) {
          setTimeout(poll, 3000);
        } else {
          setError('回测超时，请稍后查看');
          setRunning(false);
        }
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
    } catch {
      setError('加载结果失败');
    }
  };

  const deleteResult = async (id: number) => {
    try {
      await adminApi.deleteBacktestResult(id);
      setHistory(history.filter(h => h.id !== id));
      if (result?.id === id) setResult(null);
    } catch {
      setError('删除失败');
    }
  };

  const updateFactorWeight = (key: string, value: number) => {
    setParams({ ...params, factor_weights: { ...params.factor_weights, [key]: value } });
  };

  const perf = result?.performance;
  const summary = result?.summary;
  const usedParams = result?.params_used;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800">历史回测</h1>
        <p className="text-gray-500 mt-1">基于历史信号模拟交易策略，修改参数迭代优化</p>
      </div>

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

        {/* Advanced params toggle */}
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1 text-sm text-primary-600 mt-3 hover:text-primary-700"
        >
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
                  <input type="checkbox" checked={params.normalize_signals} onChange={e => setParams({ ...params, normalize_signals: e.target.checked })} className="rounded" />
                  信号归一化
                </label>
              </div>
            </div>

            {/* Factor weights */}
            <div>
              <label className="text-xs text-gray-500 block mb-2">因子权重（总和 = 1.0）</label>
              <div className="grid grid-cols-5 gap-2">
                {Object.entries(FACTOR_LABELS).map(([key, label]) => (
                  <div key={key}>
                    <label className="text-xs text-gray-400 block mb-1">{label}</label>
                    <input
                      type="number" step={0.05} min={0} max={1}
                      value={params.factor_weights[key] || 0}
                      onChange={e => updateFactorWeight(key, Number(e.target.value))}
                      className="input-field text-sm"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Buy weights & sell ratios */}
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

      {/* Loading state */}
      {running && !result && (
        <div className="card flex items-center justify-center h-48">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-3" />
            <p className="text-gray-500">回测运行中，请稍候...</p>
            <p className="text-gray-400 text-xs mt-1">通常需要 30-60 秒</p>
          </div>
        </div>
      )}

      {/* History */}
      {history.length > 0 && !running && (
        <div className="card mb-6">
          <div className="flex items-center gap-2 mb-3">
            <History size={16} className="text-gray-400" />
            <h3 className="text-sm font-semibold text-gray-700">历史记录</h3>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {history.map(item => (
              <div key={item.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50">
                <button onClick={() => loadResult(item.id)} className="flex-1 text-left">
                  <span className="text-sm font-medium text-gray-700">{item.name || `${item.start_date}~${item.end_date}`}</span>
                  <span className="text-xs text-gray-400 ml-2">{item.created_at?.slice(0, 16)}</span>
                </button>
                <div className="flex items-center gap-3">
                  <span className={`text-sm font-mono ${(item.performance?.total_return_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {item.performance?.total_return_pct > 0 ? '+' : ''}{item.performance?.total_return_pct}%
                  </span>
                  <button onClick={() => deleteResult(item.id)} className="text-gray-300 hover:text-red-500">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {result && (
        <>
          {/* Used params */}
          {usedParams && (
            <div className="card mb-6">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">回测参数</h3>
              <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                <span>资金: ¥{usedParams.initial_capital?.toLocaleString()}</span>
                <span>S权重: {usedParams.buy_weights?.S}</span>
                <span>A权重: {usedParams.buy_weights?.A}</span>
                <span>C卖出: {(usedParams.sell_ratios?.C * 100).toFixed(0)}%</span>
                <span>D卖出: {(usedParams.sell_ratios?.D * 100).toFixed(0)}%</span>
                <span>单基金上限: {(usedParams.max_single_fund_ratio * 100).toFixed(0)}%</span>
                <span>每日最多买: {usedParams.max_daily_buys}</span>
                {usedParams.normalize_signals && <span className="text-primary-600">归一化: 开</span>}
              </div>
            </div>
          )}

          {/* Summary */}
          <div className="card mb-6">
            <h2 className="text-lg font-semibold mb-4">回测概要</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-gray-500">回测区间</p>
                <p className="font-medium">{summary?.start_date} ~ {summary?.end_date}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">交易天数</p>
                <p className="font-medium">{summary?.trading_days}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">基金数量</p>
                <p className="font-medium">{summary?.funds_scored}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">信号总数</p>
                <p className="font-medium">{summary?.total_signals_generated?.toLocaleString()}</p>
              </div>
            </div>
          </div>

          {/* Performance */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
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
                <span className="text-sm text-gray-500">基准收益 (沪深300)</span>
              </div>
              <p className={`text-2xl font-bold ${(perf?.benchmark_return_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {perf?.benchmark_return_pct > 0 ? '+' : ''}{perf?.benchmark_return_pct}%
              </p>
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

          {/* Signal Distribution + Factor Contributions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">信号等级分布</h3>
              {result?.signal_distribution && Object.keys(result.signal_distribution).length > 0 ? (
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
              ) : <p className="text-gray-400 text-sm">无信号数据</p>}
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

          {/* Monthly Returns */}
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

          {/* Note */}
          {perf?.total_return_pct === 0 && (
            <div className="card border border-yellow-200 bg-yellow-50 mb-6">
              <div className="flex items-start gap-3">
                <AlertCircle size={20} className="text-yellow-600 mt-0.5 shrink-0" />
                <div>
                  <p className="font-medium text-yellow-800">回测说明</p>
                  <p className="text-sm text-yellow-700 mt-1">
                    当前回测区间内所有信号均为 B(持有)，无买入/卖出信号触发交易。
                    可尝试调整高级参数中的因子权重或信号阈值来增加信号分散度。
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Daily values */}
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
                        <td className="py-2 pr-4 font-mono">¥{dv.portfolio_value.toLocaleString()}</td>
                        <td className="py-2 pr-4">¥{dv.cash.toLocaleString()}</td>
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
      )}
    </div>
  );
}
