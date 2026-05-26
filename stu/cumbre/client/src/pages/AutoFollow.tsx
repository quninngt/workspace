import { useState, useEffect } from 'react';
import { autoApi, fundsApi } from '../api/client';
import { Settings, TrendingUp, DollarSign, PieChart, Clock, Info, Play, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { PieChart as RPieChart, Pie, Cell, ResponsiveContainer, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts';

const PLAN_TYPES = [
  { value: 'daily', label: '每日' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' },
];

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];

export default function AutoFollow() {
  const [config, setConfig] = useState<any>(null);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [reports, setReports] = useState<any[]>([]);
  const [dailyAmount, setDailyAmount] = useState('');
  const [planType, setPlanType] = useState('daily');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [execMessage, setExecMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [updatingMarket, setUpdatingMarket] = useState(false);
  const [marketMessage, setMarketMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showProfitDetail, setShowProfitDetail] = useState(false);
  const [profitDetail, setProfitDetail] = useState<any>(null);
  const [loadingProfit, setLoadingProfit] = useState(false);

  const [fundNames, setFundNames] = useState<Record<string, string>>({});

  const loadNames = async (data: any) => {
    const codes: string[] = [];
    data?.positions?.forEach((p: any) => codes.push(p.fund_code));
    data?.trades?.forEach((t: any) => codes.push(t.fund_code));
    if (codes.length) {
      const names = await fundsApi.names(codes);
      setFundNames(names);
    }
  };

  const load = async () => {
    try {
      const [c, p, r] = await Promise.all([
        autoApi.getConfig(), autoApi.getPortfolio(), autoApi.getReports(),
      ]);
      setConfig(c.data);
      setPortfolio(p.data);
      setReports(r.data || []);
      if (c.data) {
        setDailyAmount(String(c.data.daily_amount || Math.round(c.data.total_amount / 22)));
        setPlanType(c.data.plan_type || 'daily');
      }
      await loadNames(p.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [refreshKey]);

  const saveConfig = async () => {
    setSaving(true);
    try {
      const da = Number(dailyAmount);
      const res = await autoApi.saveConfig(
        Math.round(da * 22),
        da,
        planType,
      );
      setConfig(res.data);
    } finally { setSaving(false); }
  };

  const handleExecute = async () => {
    setExecuting(true);
    setExecMessage(null);
    try {
      const res = await autoApi.execute();
      setExecMessage({ type: 'success', text: res.data.message || `成功执行 ${res.data.trades_created} 笔交易` });
      setRefreshKey(k => k + 1);
    } catch (err: any) {
      setExecMessage({ type: 'error', text: err.response?.data?.detail || '执行失败' });
    } finally { setExecuting(false); }
  };

  const handleUpdateMarketValue = async () => {
    setUpdatingMarket(true);
    setMarketMessage(null);
    try {
      const res = await autoApi.updateMarketValue();
      setMarketMessage({
        type: 'success',
        text: `市值已更新: ¥${res.data.old_market_value?.toLocaleString()} → ¥${res.data.new_market_value?.toLocaleString()} (${res.data.change >= 0 ? '+' : ''}¥${res.data.change?.toLocaleString()})`
      });
      setRefreshKey(k => k + 1);
    } catch (err: any) {
      setMarketMessage({ type: 'error', text: err.response?.data?.detail || '更新失败' });
    } finally { setUpdatingMarket(false); }
  };

  const handleShowProfitDetail = async () => {
    setLoadingProfit(true);
    try {
      const res = await autoApi.getProfitDetail();
      setProfitDetail(res.data);
      // 加载基金名称
      const codes = res.data.positions?.map((p: any) => p.fund_code) || [];
      if (codes.length) {
        const names = await fundsApi.names(codes);
        setFundNames(prev => ({ ...prev, ...names }));
      }
      setShowProfitDetail(true);
    } catch (err: any) {
      console.error('Failed to load profit detail:', err);
    } finally { setLoadingProfit(false); }
  };

  // Check if currently in cooldown
  const todayStr = new Date().toISOString().slice(0, 10);
  const isCooldown = config?.last_executed_at === todayStr;

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" /></div>;

  const pieData = portfolio?.positions?.map((p: any) => ({
    name: fundNames[p.fund_code] || p.fund_code, value: p.allocation_ratio,
  })) || [];

  // Build portfolio nav history for mini chart
  const navHistory = portfolio?.nav_history
    ? (typeof portfolio.nav_history === 'string' ? JSON.parse(portfolio.nav_history) : portfolio.nav_history)
    : [];

  // Calculate portfolio return
  const totalReturn = portfolio?.total_invested > 0
    ? ((portfolio.market_value - portfolio.total_invested) / portfolio.total_invested * 100)
    : 0;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800">自动跟投</h1>
        <p className="text-gray-500 mt-1">模型验证工具 — 系统自动分配，不可手动编辑</p>
      </div>

      {/* Config */}
      <div className="card mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Settings size={20} className="text-primary-500" />
          <h2 className="text-lg font-semibold">投资配置</h2>
        </div>
        {config ? (
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">日均投入金额</p>
              <p className="text-2xl font-bold text-gray-800">¥{config.daily_amount?.toLocaleString() || Math.round(config.total_amount / 22).toLocaleString()}</p>
              <p className="text-xs text-gray-400 mt-1">月均约 ¥{(config.total_amount || config.daily_amount * 22)?.toLocaleString()}</p>
            </div>
            <span className={`text-sm px-3 py-1 rounded-full font-medium ${
              config.status === 'active' ? 'text-green-600 bg-green-50' : 'text-gray-600 bg-gray-100'
            }`}>
              {config.status === 'active' ? '运行中' : '已暂停'}
            </span>
          </div>
        ) : (
          <p className="text-gray-400 text-sm mb-4">尚未设置日均投入金额。设置后系统将自动生成投资组合。</p>
        )}
        <div className="mt-4 pt-4 border-t">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3">
            <div className="relative w-full sm:flex-1 sm:max-w-xs">
              <DollarSign size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="number"
                value={dailyAmount}
                onChange={e => setDailyAmount(e.target.value)}
                placeholder="输入日均投入金额"
                className="input-field pl-9"
              />
            </div>
            <div className="w-full sm:w-auto">
              <label className="text-xs text-gray-500 block mb-1">执行频率</label>
              <select value={planType} onChange={e => setPlanType(e.target.value)} className="input-field text-sm py-2 w-full sm:w-auto">
                {PLAN_TYPES.map(pt => <option key={pt.value} value={pt.value}>{pt.label}</option>)}
              </select>
            </div>
            <button onClick={saveConfig} disabled={saving || !dailyAmount} className="btn-primary w-full sm:w-auto">
              {saving ? '保存中...' : (config ? '更新设置' : '启动跟投')}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2 flex items-center gap-1">
            <Info size={12} />
            系统将根据策略频率自动计算：每周投入 ≈ 日均 × 5，每月投入 ≈ 日均 × 22
          </p>
        </div>

        {/* Execute section */}
        {config && config.daily_amount > 0 && (
          <div className="mt-4 pt-4 border-t flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Play size={16} className="text-primary-500" />
              <span className="text-sm text-gray-600">立即执行跟投</span>
              {isCooldown && (
                <span className="text-xs text-gray-400 flex items-center gap-1">
                  <CheckCircle size={12} className="text-green-500" /> 今日已执行
                </span>
              )}
              {config.last_executed_at && !isCooldown && (
                <span className="text-xs text-gray-400">
                  上次执行: {config.last_executed_at}
                </span>
              )}
            </div>
            <button
              onClick={handleExecute}
              disabled={executing || isCooldown}
              className={`btn-primary flex items-center gap-2 ${isCooldown ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {executing ? (
                <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" /> 执行中...</>
              ) : (
                <><Play size={16} /> {isCooldown ? '今日已执行' : '立即执行'}</>
              )}
            </button>
          </div>
        )}

        {/* Execution feedback */}
        {execMessage && (
          <div className={`mt-3 px-4 py-3 rounded-lg flex items-center gap-2 text-sm ${
            execMessage.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
          }`}>
            {execMessage.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            {execMessage.text}
            <button onClick={() => setExecMessage(null)} className="ml-auto font-medium hover:underline">关闭</button>
          </div>
        )}
      </div>

      {/* Update Market Value */}
      {portfolio && (
        <div className="card mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <RefreshCw size={16} className="text-primary-500" />
              <span className="text-sm text-gray-600">市值更新</span>
              <span className="text-xs text-gray-400">根据最新净值重新计算持仓市值</span>
            </div>
            <button
              onClick={handleUpdateMarketValue}
              disabled={updatingMarket}
              className="btn-secondary flex items-center gap-2"
            >
              {updatingMarket ? (
                <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600" /> 更新中...</>
              ) : (
                <><RefreshCw size={16} /> 更新市值</>
              )}
            </button>
          </div>
          {marketMessage && (
            <div className={`mt-3 px-4 py-3 rounded-lg flex items-center gap-2 text-sm ${
              marketMessage.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
            }`}>
              {marketMessage.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
              {marketMessage.text}
              <button onClick={() => setMarketMessage(null)} className="ml-auto font-medium hover:underline">关闭</button>
            </div>
          )}
        </div>
      )}

      {portfolio && (
        <>
          {/* Portfolio Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="card">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-500">总投入</span>
                <TrendingUp className="text-blue-500" size={20} />
              </div>
              <p className="text-2xl font-bold text-gray-800">¥{portfolio.total_invested?.toLocaleString()}</p>
            </div>
            <div className="card">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-500">当前市值</span>
                <DollarSign className="text-green-500" size={20} />
              </div>
              <p className="text-2xl font-bold text-green-600">¥{portfolio.market_value?.toLocaleString()}</p>
            </div>
            <div className="card cursor-pointer hover:shadow-md transition-shadow" onClick={handleShowProfitDetail}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-500">累计收益</span>
                <TrendingUp className={totalReturn >= 0 ? 'text-green-500' : 'text-red-500'} size={20} />
              </div>
              <p className={`text-2xl font-bold ${totalReturn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%
              </p>
              <p className="text-xs text-gray-400 mt-1">点击查看基金贡献</p>
            </div>
            <div className="card">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-500">可用现金</span>
                <DollarSign className="text-yellow-500" size={20} />
              </div>
              <p className="text-2xl font-bold text-gray-800">¥{portfolio.cash?.toLocaleString()}</p>
            </div>
          </div>

          {/* Portfolio Nav Mini Chart */}
          {navHistory.length > 1 && (
            <div className="card mb-6">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp size={18} className="text-primary-500" />
                <h2 className="text-lg font-semibold">组合净值走势</h2>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={navHistory}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v?.slice(5) || ''} />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} dot={false} name="组合价值" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Positions */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <div className="lg:col-span-2 card overflow-hidden">
              <h2 className="text-lg font-semibold mb-4 px-5 pt-5">持仓明细</h2>
              {portfolio.positions?.length === 0 ? (
                <p className="text-gray-400 text-center py-8">暂无持仓</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr className="border-b text-left text-sm text-gray-500">
                        <th className="px-4 py-3 font-medium">基金</th>
                        <th className="px-4 py-3 font-medium">份额</th>
                        <th className="px-4 py-3 font-medium">成本净值</th>
                        <th className="px-4 py-3 font-medium">占比</th>
                      </tr>
                    </thead>
                    <tbody>
                      {portfolio.positions?.map((p: any) => (
                        <tr key={p.id} className="border-b last:border-0">
                          <td className="px-4 py-3 text-sm">
                            <span className="font-mono text-primary-600">{p.fund_code}</span>
                            {fundNames[p.fund_code] && <span className="text-gray-500 ml-2">{fundNames[p.fund_code]}</span>}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">{p.shares?.toFixed(2)}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{p.cost_nav?.toFixed(4)}</td>
                          <td className="px-4 py-3 text-sm font-medium">{(p.allocation_ratio * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Allocation Pie */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">资产配置</h2>
              {pieData.length === 0 ? (
                <p className="text-gray-400 text-center py-8">暂无配置</p>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <RPieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}>
                      {pieData.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                  </RPieChart>
                </ResponsiveContainer>
              )}
              <div className="space-y-1 mt-2">
                {pieData.map((d: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                    <span className="text-gray-500">{d.name}</span>
                    <span className="font-medium text-gray-700">{(d.value * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Trades */}
          <div className="card overflow-hidden mb-6">
            <h2 className="text-lg font-semibold mb-4 px-5 pt-5">交易记录</h2>
            {portfolio.trades?.length === 0 ? (
              <p className="text-gray-400 text-center py-8">暂无交易</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr className="border-b text-left text-sm text-gray-500">
                      <th className="px-4 py-3 font-medium">日期</th>
                      <th className="px-4 py-3 font-medium">基金</th>
                      <th className="px-4 py-3 font-medium">类型</th>
                      <th className="px-4 py-3 font-medium">金额</th>
                      <th className="px-4 py-3 font-medium">份额</th>
                      <th className="px-4 py-3 font-medium">净值</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portfolio.trades?.map((t: any) => (
                      <tr key={t.id} className="border-b last:border-0">
                        <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">{t.date}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className="font-mono text-primary-600">{t.fund_code}</span>
                          {fundNames[t.fund_code] && <span className="text-gray-500 ml-2">{fundNames[t.fund_code]}</span>}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-1 rounded-full font-medium whitespace-nowrap ${t.type === 'buy' ? 'text-green-600 bg-green-50' : 'text-red-600 bg-red-50'}`}>
                            {t.type === 'buy' ? '买入' : '卖出'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">¥{t.amount?.toLocaleString()}</td>
                        <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{t.shares?.toFixed(2)}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">{t.nav?.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Reports */}
          {reports.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">收益报告</h2>
              <div className="space-y-3">
                {reports.map(r => (
                  <div key={r.id} className="flex items-center justify-between py-2 border-b last:border-0">
                    <div className="flex items-center gap-2">
                      <Clock size={16} className="text-gray-400" />
                      <span className="text-sm text-gray-700">{r.period_start} ~ {r.period_end}</span>
                    </div>
                    <span className="text-sm text-gray-500">{r.period_type === 'monthly' ? '月度' : r.period_type === 'quarterly' ? '季度' : '年度'}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Profit Detail Modal */}
      {showProfitDetail && profitDetail && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowProfitDetail(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-3xl mx-4 shadow-xl max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">收益明细 - 各基金贡献</h3>

            {/* Summary */}
            <div className="grid grid-cols-3 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="text-sm text-gray-500">总投入</p>
                <p className="text-lg font-bold text-gray-800">¥{profitDetail.total_invested?.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">当前市值</p>
                <p className="text-lg font-bold text-green-600">¥{profitDetail.total_market_value?.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">总盈亏</p>
                <p className={`text-lg font-bold ${profitDetail.total_profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {profitDetail.total_profit_loss >= 0 ? '+' : ''}¥{profitDetail.total_profit_loss?.toLocaleString()}
                  <span className="text-sm ml-2">({profitDetail.total_profit_loss_ratio >= 0 ? '+' : ''}{profitDetail.total_profit_loss_ratio?.toFixed(2)}%)</span>
                </p>
              </div>
            </div>

            {/* Position Details */}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr className="border-b text-left text-sm text-gray-500">
                    <th className="px-4 py-3 font-medium">基金</th>
                    <th className="px-4 py-3 font-medium">份额</th>
                    <th className="px-4 py-3 font-medium">成本/现价</th>
                    <th className="px-4 py-3 font-medium">市值</th>
                    <th className="px-4 py-3 font-medium">盈亏</th>
                    <th className="px-4 py-3 font-medium">占比</th>
                  </tr>
                </thead>
                <tbody>
                  {profitDetail.positions?.map((pos: any) => (
                    <tr key={pos.fund_code} className="border-b last:border-0">
                      <td className="px-4 py-3 text-sm">
                        <span className="font-mono text-primary-600">{pos.fund_code}</span>
                        {fundNames[pos.fund_code] && <div className="text-xs text-gray-400">{fundNames[pos.fund_code]}</div>}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">{pos.shares.toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm">
                        <div className="text-gray-600">{pos.cost_nav.toFixed(4)}</div>
                        <div className="text-xs text-gray-400">→ {pos.current_nav.toFixed(4)}</div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">¥{pos.market_value.toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm whitespace-nowrap">
                        <div className={pos.profit_loss >= 0 ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
                          {pos.profit_loss >= 0 ? '+' : ''}¥{pos.profit_loss.toLocaleString()}
                        </div>
                        <div className={`text-xs ${pos.profit_loss_ratio >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                          {pos.profit_loss_ratio >= 0 ? '+' : ''}{pos.profit_loss_ratio}%
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{(pos.allocation_ratio * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end mt-4">
              <button onClick={() => setShowProfitDetail(false)} className="btn-primary">关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
