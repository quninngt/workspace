import { useState } from 'react';
import { toolsApi, adminApi } from '../api/client';
import { Wrench, AlertTriangle, RefreshCw, CheckCircle, Database, Zap, PieChart, DownloadCloud, Activity, Cpu, Info, Server } from 'lucide-react';

interface ActionCard {
  key: string;
  title: string;
  description: string;
  icon: any;
  action: () => Promise<any>;
  danger?: boolean;
  confirmOnly?: boolean;
}

export default function Tools() {
  const [confirming, setConfirming] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState('');
  const [result, setResult] = useState<{ key: string; ok: boolean; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [runningJobs, setRunningJobs] = useState<Set<string>>(new Set());

  const showResult = (key: string, ok: boolean, msg: string) => {
    setResult({ key, ok, msg });
    setTimeout(() => setResult(null), 5000);
  };

  // Manual trigger cards (one-click, no confirmation needed)
  const triggerCards: ActionCard[] = [
    {
      key: 'sync-funds',
      title: '同步基金列表',
      description: '从天天基金同步全市场基金列表，新增基金数据。',
      icon: DownloadCloud,
      action: () => adminApi.syncFunds(),
    },
    {
      key: 'sync-nav',
      title: '同步净值数据',
      description: '从天天基金同步所有基金的净值数据，通常需要几分钟。',
      icon: Activity,
      action: () => adminApi.syncNav(),
    },
    {
      key: 'sync-nav-full',
      title: '全量净值同步',
      description: '重新拉取全部基金的历史净值（耗时较长），首次使用或数据不完整时执行。',
      icon: Server,
      action: () => adminApi.syncNavFull(),
    },
    {
      key: 'gen-signals',
      title: '生成信号评分',
      description: '基于最新净值数据，运行信号引擎为所有基金生成买卖信号。',
      icon: Cpu,
      action: () => adminApi.generateSignals(),
    },
  ];

  // Reset cards (need confirmation)
  const resetCards: ActionCard[] = [
    {
      key: 'reset-auto',
      title: '重置自动跟投数据',
      description: '清空自动跟投配置、投资组合、持仓、交易记录和收益报告。',
      icon: Zap,
      action: () => toolsApi.resetAuto(),
    },
    {
      key: 'reset-manual',
      title: '重置手动跟投数据',
      description: '清空执行清单、手动投资组合、持仓和交易记录。',
      icon: Database,
      action: () => toolsApi.resetManual(),
    },
    {
      key: 'reset-signals',
      title: '重置所有信号数据',
      description: '清空全部基金信号评分。这将影响所有用户的信号数据。',
      icon: PieChart,
      action: () => toolsApi.resetSignals(),
      danger: true,
    },
  ];

  const handleTrigger = async (card: ActionCard) => {
    setRunningJobs(prev => new Set(prev).add(card.key));
    try {
      const res = await card.action();
      showResult(card.key, true, res.data.message || '任务已启动，后台执行中');
    } catch (err: any) {
      showResult(card.key, false, err.response?.data?.detail || '操作失败');
    } finally {
      setRunningJobs(prev => {
        const next = new Set(prev);
        next.delete(card.key);
        return next;
      });
    }
  };

  const handleReset = async (card: ActionCard) => {
    if (confirmText !== '确认') return;
    setBusy(true);
    try {
      const res = await card.action();
      showResult(card.key, true, `成功清除 ${res.data.deleted} 条记录`);
    } catch (err: any) {
      showResult(card.key, false, err.response?.data?.detail || '操作失败');
    } finally {
      setBusy(false);
      setConfirming(null);
      setConfirmText('');
    }
  };

  const isRunning = (key: string) => runningJobs.has(key);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800">工具箱</h1>
        <p className="text-gray-500 mt-1">系统工具和数据管理</p>
      </div>

      {/* Result Toast */}
      {result && (
        <div className={`mb-4 px-4 py-3 rounded-lg flex items-center gap-2 text-sm ${
          result.ok ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-600 border border-red-200'
        }`}>
          {result.ok ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          {result.msg}
          <button onClick={() => setResult(null)} className="ml-auto font-medium hover:underline">关闭</button>
        </div>
      )}

      {/* Manual Trigger Section */}
      <h2 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
        <Cpu size={20} className="text-primary-500" />
        手动触发
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        {triggerCards.map(card => (
          <div key={card.key} className="card">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-primary-50">
                <card.icon size={24} className="text-primary-600" />
              </div>
              <h2 className="font-semibold text-gray-800">{card.title}</h2>
            </div>
            <p className="text-sm text-gray-500 mb-4">{card.description}</p>
            <button
              onClick={() => handleTrigger(card)}
              disabled={isRunning(card.key)}
              className="w-full py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2 bg-primary-50 text-primary-600 hover:bg-primary-100 disabled:opacity-50"
            >
              {isRunning(card.key) ? (
                <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600" /> 执行中...</>
              ) : (
                <><RefreshCw size={14} /> 开始执行</>
              )}
            </button>
          </div>
        ))}
      </div>

      {/* Data Reset Section */}
      <h2 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
        <AlertTriangle size={20} className="text-orange-500" />
        数据重置
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {resetCards.map(card => (
          <div key={card.key} className={`card ${card.danger ? 'border-red-200' : ''}`}>
            <div className="flex items-center gap-3 mb-4">
              <div className={`p-2 rounded-lg ${card.danger ? 'bg-red-50' : 'bg-gray-50'}`}>
                <card.icon size={24} className={card.danger ? 'text-red-500' : 'text-gray-600'} />
              </div>
              <h2 className="font-semibold text-gray-800">{card.title}</h2>
            </div>
            <p className="text-sm text-gray-500 mb-4">{card.description}</p>

            {confirming === card.key ? (
              <div className="space-y-3">
                <p className="text-sm font-medium text-orange-600">请输入"确认"以继续</p>
                <input
                  type="text"
                  value={confirmText}
                  onChange={e => setConfirmText(e.target.value)}
                  placeholder="输入 确认"
                  className="input-field text-sm"
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => handleReset(card)}
                    disabled={confirmText !== '确认' || busy}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium text-white transition-colors ${
                      card.danger ? 'bg-red-500 hover:bg-red-600' : 'bg-orange-500 hover:bg-orange-600'
                    } disabled:opacity-40`}
                  >
                    {busy ? '处理中...' : '确认重置'}
                  </button>
                  <button
                    onClick={() => { setConfirming(null); setConfirmText(''); }}
                    className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-600 hover:bg-gray-200"
                  >
                    取消
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setConfirming(card.key)}
                className={`w-full py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
                  card.danger
                    ? 'bg-red-50 text-red-600 hover:bg-red-100'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                <RefreshCw size={14} /> 重置
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="mt-8 card bg-blue-50 border-blue-200">
        <div className="flex items-start gap-3">
          <Info size={20} className="text-blue-600 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium text-blue-800">说明</p>
            <ul className="text-sm text-blue-700 mt-1 space-y-1">
              <li>• 「手动触发」的任务在后台异步执行，点击后关闭页面不影响执行</li>
              <li>• 增量同步只拉取最新净值（快），全量同步重新拉取历史全部净值（慢但完整）</li>
              <li>• 同步基金列表约 1-2 分钟，同步净值取决于基金数量</li>
              <li>• 生成信号前请确保净值数据已同步</li>
              <li>• 重置操作不可撤销，建议在重置前确认数据不再需要</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
