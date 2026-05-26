import { useState, useEffect } from 'react';
import { executionApi, fundsApi, manualApi } from '../api/client';
import { Plus, Trash2, Check, X, TrendingUp, TrendingDown, Minus, Send, RefreshCw, ChevronLeft, ChevronRight, CheckSquare, DollarSign, PieChart, BarChart3 } from 'lucide-react';

const STATUS_UI: Record<string, { label: string; class: string }> = {
  pending: { label: '待执行', class: 'text-yellow-600 bg-yellow-50' },
  executed: { label: '已执行', class: 'text-green-600 bg-green-50' },
  skipped: { label: '已跳过', class: 'text-gray-500 bg-gray-100' },
};

const ACTION_UI: Record<string, { label: string; icon: any; class: string }> = {
  buy: { label: '买入', icon: TrendingUp, class: 'text-green-600 bg-green-50' },
  sell: { label: '卖出', icon: TrendingDown, class: 'text-red-600 bg-red-50' },
  hold: { label: '持有', icon: Minus, class: 'text-gray-600 bg-gray-100' },
};

const PAGE_SIZE = 20;

export default function ManualFollow() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitResult, setSubmitResult] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);
  const [genLoading, setGenLoading] = useState(false);
  const [genMessage, setGenMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [form, setForm] = useState({ fund_code: '', action: 'buy' as string, amount_min: '', amount_max: '' });
  const [fundNames, setFundNames] = useState<Record<string, string>>({});
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [portfolioSummary, setPortfolioSummary] = useState<any>(null);
  const [showProfitDetail, setShowProfitDetail] = useState(false);
  const [showPositionDetail, setShowPositionDetail] = useState(false);

  const loadNames = async (data: any[]) => {
    const codes = data.map(i => i.fund_code);
    if (codes.length) {
      const names = await fundsApi.names(codes);
      setFundNames(names);
    }
  };

  const loadPortfolioSummary = async () => {
    try {
      const res = await manualApi.getPortfolioSummary();
      setPortfolioSummary(res.data);
    } catch (err) {
      console.error('Failed to load portfolio summary:', err);
    }
  };

  const load = async () => {
    setLoading(true);
    try {
      const params: any = { skip: page * PAGE_SIZE, limit: PAGE_SIZE };
      if (statusFilter) params.status = statusFilter;
      const res = await executionApi.list(params);
      setItems(res.data);
      setTotal(res.total);
      await loadNames(res.data);
      await loadPortfolioSummary();
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [page, statusFilter]);

  const handleCreate = async () => {
    await executionApi.create({
      fund_code: form.fund_code,
      action: form.action,
      suggested_amount_min: form.amount_min ? Number(form.amount_min) : undefined,
      suggested_amount_max: form.amount_max ? Number(form.amount_max) : undefined,
    });
    setShowForm(false);
    setForm({ fund_code: '', action: 'buy', amount_min: '', amount_max: '' });
    load();
  };

  const handleStatus = async (id: number, status: string) => {
    await executionApi.update(id, { status });
    setSelectedIds(new Set());
    load();
  };

  const handleDelete = async (id: number) => {
    await executionApi.delete(id);
    load();
  };

  const handleBatchStatus = async (status: string) => {
    await executionApi.updateBatch([...selectedIds], { status });
    setSelectedIds(new Set());
    load();
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const res = await executionApi.submit();
      setSubmitResult(res.data);
      setShowConfirm(false);
      load();
    } finally { setSubmitting(false); }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map(i => i.id)));
    }
  };

  const pendingCount = total;

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">执行清单</h1>
          <p className="text-gray-500 mt-1">查看和管理投资执行计划</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={async () => {
            setGenLoading(true);
            setGenMessage(null);
            try {
              const res = await executionApi.generateFromSignals();
              setGenMessage({ type: 'success', text: `成功生成 ${res.data.created} 条执行项目` });
              load();
            } catch (err: any) {
              setGenMessage({ type: 'error', text: err.response?.data?.detail || '生成失败，请检查今日是否有信号' });
            } finally { setGenLoading(false); }
          }} disabled={genLoading} className="btn-secondary flex items-center gap-2">
            <RefreshCw size={16} className={genLoading ? 'animate-spin' : ''} /> {genLoading ? '生成中...' : '从信号生成'}
          </button>
          <button onClick={() => setShowForm(true)} className="btn-secondary flex items-center gap-2">
            <Plus size={16} /> 添加
          </button>
          {pendingCount > 0 && (
            <button onClick={() => setShowConfirm(true)} className="btn-primary flex items-center gap-2">
              <Send size={16} /> 提交执行 ({pendingCount})
            </button>
          )}
        </div>
      </div>

      {/* Portfolio Summary Cards */}
      {portfolioSummary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="card cursor-pointer hover:shadow-md transition-shadow" onClick={() => setShowPositionDetail(true)}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-500">总投入</span>
              <DollarSign className="text-blue-500" size={20} />
            </div>
            <p className="text-2xl font-bold text-gray-800">¥{portfolioSummary.total_invested?.toLocaleString()}</p>
            <p className="text-xs text-gray-400 mt-1">点击查看持仓详情</p>
          </div>
          <div className="card cursor-pointer hover:shadow-md transition-shadow" onClick={() => setShowPositionDetail(true)}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-500">当前市值</span>
              <PieChart className="text-green-500" size={20} />
            </div>
            <p className="text-2xl font-bold text-green-600">¥{portfolioSummary.total_market_value?.toLocaleString()}</p>
            <p className="text-xs text-gray-400 mt-1">{portfolioSummary.positions?.length || 0} 只基金</p>
          </div>
          <div className="card cursor-pointer hover:shadow-md transition-shadow" onClick={() => setShowProfitDetail(true)}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-500">总盈亏</span>
              <TrendingUp className={portfolioSummary.total_profit_loss >= 0 ? 'text-green-500' : 'text-red-500'} size={20} />
            </div>
            <p className={`text-2xl font-bold ${portfolioSummary.total_profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {portfolioSummary.total_profit_loss >= 0 ? '+' : ''}¥{portfolioSummary.total_profit_loss?.toLocaleString()}
            </p>
            <p className="text-xs text-gray-400 mt-1">点击查看盈亏明细</p>
          </div>
          <div className="card cursor-pointer hover:shadow-md transition-shadow" onClick={() => setShowProfitDetail(true)}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-500">收益率</span>
              <BarChart3 className={portfolioSummary.total_profit_loss_ratio >= 0 ? 'text-green-500' : 'text-red-500'} size={20} />
            </div>
            <p className={`text-2xl font-bold ${portfolioSummary.total_profit_loss_ratio >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {portfolioSummary.total_profit_loss_ratio >= 0 ? '+' : ''}{portfolioSummary.total_profit_loss_ratio?.toFixed(2)}%
            </p>
            <p className="text-xs text-gray-400 mt-1">点击查看贡献分析</p>
          </div>
        </div>
      )}

      {/* Profit Detail Modal */}
      {showProfitDetail && portfolioSummary && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowProfitDetail(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-2xl mx-4 shadow-xl max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">盈亏明细</h3>
            <div className="space-y-3">
              {portfolioSummary.positions?.map((pos: any) => (
                <div key={pos.fund_code} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <span className="font-mono text-primary-600">{pos.fund_code}</span>
                    {fundNames[pos.fund_code] && <span className="text-gray-500 ml-2">{fundNames[pos.fund_code]}</span>}
                    <div className="text-xs text-gray-400 mt-1">
                      {pos.shares.toFixed(2)} 份 | 成本: {pos.cost_nav.toFixed(4)} | 现价: {pos.current_nav.toFixed(4)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`font-medium ${pos.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {pos.profit_loss >= 0 ? '+' : ''}¥{pos.profit_loss.toLocaleString()}
                    </div>
                    <div className={`text-sm ${pos.profit_loss_ratio >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {pos.profit_loss_ratio >= 0 ? '+' : ''}{pos.profit_loss_ratio}%
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex justify-end mt-4">
              <button onClick={() => setShowProfitDetail(false)} className="btn-primary">关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* Position Detail Modal */}
      {showPositionDetail && portfolioSummary && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowPositionDetail(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-3xl mx-4 shadow-xl max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">持仓概览</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr className="border-b text-left text-sm text-gray-500">
                    <th className="px-4 py-3 font-medium">基金</th>
                    <th className="px-4 py-3 font-medium">份额</th>
                    <th className="px-4 py-3 font-medium">成本净值</th>
                    <th className="px-4 py-3 font-medium">最新净值</th>
                    <th className="px-4 py-3 font-medium">市值</th>
                    <th className="px-4 py-3 font-medium">盈亏</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolioSummary.positions?.map((pos: any) => (
                    <tr key={pos.fund_code} className="border-b last:border-0">
                      <td className="px-4 py-3 text-sm">
                        <span className="font-mono text-primary-600">{pos.fund_code}</span>
                        {fundNames[pos.fund_code] && <div className="text-xs text-gray-400">{fundNames[pos.fund_code]}</div>}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">{pos.shares.toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{pos.cost_nav.toFixed(4)}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{pos.current_nav.toFixed(4)}</td>
                      <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">¥{pos.market_value.toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm whitespace-nowrap">
                        <div className={pos.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}>
                          {pos.profit_loss >= 0 ? '+' : ''}¥{pos.profit_loss.toLocaleString()}
                        </div>
                        <div className={`text-xs ${pos.profit_loss_ratio >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                          {pos.profit_loss_ratio >= 0 ? '+' : ''}{pos.profit_loss_ratio}%
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end mt-4">
              <button onClick={() => setShowPositionDetail(false)} className="btn-primary">关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* Feedback Toast */}
      {genMessage && (
        <div className={`mb-4 px-4 py-3 rounded-lg flex items-center gap-2 text-sm ${
          genMessage.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
        }`}>
          {genMessage.text}
          <button onClick={() => setGenMessage(null)} className="ml-auto font-medium hover:underline">关闭</button>
        </div>
      )}

      {/* Status Filter + Batch Actions */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1">
          {['', 'pending', 'executed', 'skipped'].map(s => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(0); setSelectedIds(new Set()); }}
              className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                statusFilter === s ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              {s ? STATUS_UI[s]?.label || s : '全部'}
            </button>
          ))}
        </div>
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">已选 {selectedIds.size} 项</span>
            <button onClick={() => handleBatchStatus('executed')} className="btn-secondary text-xs py-1 px-2 flex items-center gap-1">
              <Check size={14} /> 批量执行
            </button>
            <button onClick={() => handleBatchStatus('skipped')} className="btn-secondary text-xs py-1 px-2 flex items-center gap-1">
              <X size={14} /> 批量跳过
            </button>
          </div>
        )}
      </div>

      {/* Submit Confirmation Modal */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowConfirm(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-sm mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-2">确认提交执行</h3>
            <p className="text-sm text-gray-500 mb-4">
              将提交 <span className="font-medium text-gray-800">{pendingCount}</span> 项待执行项目到手动组合。Buy 项将创建买入交易，Sell 项将创建卖出交易，Hold 项将被跳过。
            </p>
            <p className="text-xs text-gray-400 mb-4">提交后不可撤销。</p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setShowConfirm(false)} className="btn-secondary">取消</button>
              <button onClick={() => handleSubmit()} disabled={submitting} className="btn-primary">
                {submitting ? '提交中...' : '确认提交'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Submit Result Modal */}
      {submitResult && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setSubmitResult(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-sm mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-2">提交完成</h3>
            {submitResult.trades_created > 0 ? (
              <div className="space-y-2 text-sm">
                <p className="text-green-600 font-medium">成功创建 {submitResult.trades_created} 笔交易</p>
                <p className="text-gray-500">总金额: ¥{submitResult.total_amount?.toLocaleString() || '0'}</p>
                {submitResult.portfolio_name && (
                  <p className="text-gray-500">组合: {submitResult.portfolio_name}</p>
                )}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">没有需要执行的项目。</p>
            )}
            <div className="flex justify-end mt-4">
              <button onClick={() => setSubmitResult(null)} className="btn-primary">知道了</button>
            </div>
          </div>
        </div>
      )}

      {/* Add Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">添加执行项目</h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-gray-500 block mb-1">基金代码</label>
                <input value={form.fund_code} onChange={e => setForm({ ...form, fund_code: e.target.value })} className="input-field" placeholder="例如 000001" />
              </div>
              <div>
                <label className="text-sm text-gray-500 block mb-1">操作</label>
                <select value={form.action} onChange={e => setForm({ ...form, action: e.target.value })} className="input-field">
                  <option value="buy">买入</option>
                  <option value="sell">卖出</option>
                  <option value="hold">持有</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm text-gray-500 block mb-1">建议金额(最小)</label>
                  <input type="number" value={form.amount_min} onChange={e => setForm({ ...form, amount_min: e.target.value })} className="input-field" placeholder="0" />
                </div>
                <div>
                  <label className="text-sm text-gray-500 block mb-1">建议金额(最大)</label>
                  <input type="number" value={form.amount_max} onChange={e => setForm({ ...form, amount_max: e.target.value })} className="input-field" placeholder="0" />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowForm(false)} className="btn-secondary">取消</button>
              <button onClick={handleCreate} disabled={!form.fund_code} className="btn-primary">添加</button>
            </div>
          </div>
        </div>
      )}

      {/* List */}
      <div className="card overflow-hidden p-0">
        {loading ? (
          <div className="flex items-center justify-center h-48"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" /></div>
        ) : items.length === 0 ? (
          <p className="text-gray-400 text-center py-12">暂无执行项目</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr className="border-b bg-gray-50 text-left text-sm text-gray-500">
                  <th className="px-4 py-3 w-10">
                    <input
                      type="checkbox"
                      checked={items.length > 0 && selectedIds.size === items.length}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-300"
                    />
                  </th>
                  <th className="px-4 py-3 font-medium">基金代码</th>
                  <th className="px-4 py-3 font-medium">操作</th>
                  <th className="px-4 py-3 font-medium">建议金额</th>
                  <th className="px-4 py-3 font-medium">状态</th>
                  <th className="px-4 py-3 font-medium">日期</th>
                  <th className="px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
              {items.map(item => {
                const act = ACTION_UI[item.action] || ACTION_UI.hold;
                const ActIcon = act.icon;
                return (
                  <tr key={item.id} className={`border-b last:border-0 hover:bg-gray-50 ${selectedIds.has(item.id) ? 'bg-primary-50' : ''}`}>
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.id)}
                        onChange={() => toggleSelect(item.id)}
                        className="rounded border-gray-300"
                      />
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className="font-mono text-primary-600">{item.fund_code}</span>
                      {fundNames[item.fund_code] && <span className="text-gray-500 ml-2">{fundNames[item.fund_code]}</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-medium ${act.class}`}>
                        <ActIcon size={12} /> {act.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {item.suggested_amount_min || item.suggested_amount_max
                        ? `¥${item.suggested_amount_min?.toLocaleString() || '0'} ~ ¥${item.suggested_amount_max?.toLocaleString() || '0'}`
                        : '--'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_UI[item.status]?.class || ''}`}>
                        {STATUS_UI[item.status]?.label || item.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">{item.date}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        {item.status === 'pending' && (
                          <>
                            <button onClick={() => handleStatus(item.id, 'executed')} className="p-1.5 hover:bg-green-50 rounded-lg" title="标记为已执行">
                              <Check size={16} className="text-green-500" />
                            </button>
                            <button onClick={() => handleStatus(item.id, 'skipped')} className="p-1.5 hover:bg-gray-100 rounded-lg" title="跳过">
                              <X size={16} className="text-gray-400" />
                            </button>
                          </>
                        )}
                        <button onClick={() => handleDelete(item.id)} className="p-1.5 hover:bg-red-50 rounded-lg" title="删除">
                          <Trash2 size={16} className="text-red-400" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">共 {total} 项</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={18} className="text-gray-600" />
            </button>
            <span className="text-sm text-gray-600 px-3">{page + 1} / {totalPages}</span>
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight size={18} className="text-gray-600" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
