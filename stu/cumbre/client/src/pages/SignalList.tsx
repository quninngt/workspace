import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { signalsApi } from '../api/client';
import { TrendingUp, TrendingDown, Minus, ChevronLeft, ChevronRight, Filter } from 'lucide-react';

const LEVEL_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  S: { label: '强买入', color: 'text-green-700', bg: 'bg-green-50 border-green-200' },
  A: { label: '买入', color: 'text-blue-700', bg: 'bg-blue-50 border-blue-200' },
  B: { label: '持有', color: 'text-yellow-700', bg: 'bg-yellow-50 border-yellow-200' },
  C: { label: '卖出', color: 'text-orange-700', bg: 'bg-orange-50 border-orange-200' },
  D: { label: '强卖出', color: 'text-red-700', bg: 'bg-red-50 border-red-200' },
};

const LEVELS = ['', 'S', 'A', 'B', 'C', 'D'];

export default function SignalList() {
  const { level: urlLevel } = useParams<{ level: string }>();
  const navigate = useNavigate();
  const [signals, setSignals] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [level, setLevel] = useState(urlLevel || '');
  const pageSize = 30;

  useEffect(() => {
    if (urlLevel) setLevel(urlLevel);
  }, [urlLevel]);

  const load = async () => {
    setLoading(true);
    try {
      const params: any = { skip: page * pageSize, limit: pageSize };
      if (level) params.level = level;
      const res = await signalsApi.list(params);
      setSignals(res.data);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, level]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800">信号列表</h1>
        <p className="text-gray-500 mt-1">全市场基金信号评分详情</p>
      </div>

      {/* Level Filter */}
      <div className="flex items-center gap-2 mb-4">
        <Filter size={16} className="text-gray-400" />
        {LEVELS.map(l => (
          <button
            key={l}
            onClick={() => { setLevel(l); setPage(0); }}
            className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
              level === l
                ? 'bg-primary-100 text-primary-700'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
          >
            {l || '全部'}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card overflow-hidden p-0">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
          </div>
        ) : signals.length === 0 ? (
          <div className="text-center py-12">
            <Filter size={36} className="mx-auto text-gray-300 mb-2" />
            <p className="text-gray-400">暂无信号数据</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b bg-gray-50 text-left text-sm text-gray-500">
                <th className="px-4 py-3 font-medium">基金代码</th>
                <th className="px-4 py-3 font-medium">基金名称</th>
                <th className="px-4 py-3 font-medium">评分</th>
                <th className="px-4 py-3 font-medium">等级</th>
                <th className="px-4 py-3 font-medium">建议操作</th>
                <th className="px-4 py-3 font-medium">推荐理由</th>
                <th className="px-4 py-3 font-medium">日期</th>
              </tr>
            </thead>
            <tbody>
              {signals.map(s => {
                const cfg = LEVEL_CONFIG[s.level] || LEVEL_CONFIG.B;
                const ActionIcon = s.action === 'buy' ? TrendingUp : s.action === 'sell' ? TrendingDown : Minus;
                const actionLabel = s.action === 'buy' ? '买入' : s.action === 'sell' ? '卖出' : '持有';
                return (
                  <tr
                    key={s.id}
                    className="border-b last:border-0 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/funds/${s.fund_code}`)}
                  >
                    <td className="px-4 py-3 text-sm font-mono text-primary-600">{s.fund_code}</td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-800 max-w-[240px] truncate">
                      {s.fund_name || '--'}
                    </td>
                    <td className="px-4 py-3 text-sm font-bold text-gray-700">{s.score?.toFixed(1)}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-bold border ${cfg.bg} ${cfg.color}`}>
                        {s.level}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-medium ${
                        s.action === 'buy' ? 'text-green-600 bg-green-50' :
                        s.action === 'sell' ? 'text-red-600 bg-red-50' :
                        'text-gray-600 bg-gray-100'
                      }`}>
                        <ActionIcon size={12} /> {actionLabel}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600 max-w-[200px]">
                      {s.recommendation?.short ? (
                        <span className="line-clamp-2 hover:text-primary-600 cursor-help" title={s.recommendation.professional || s.recommendation.short}>
                          {s.recommendation.short}
                        </span>
                      ) : (
                        <span className="text-gray-300">--</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">{s.date}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">共 {total} 条信号</p>
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
