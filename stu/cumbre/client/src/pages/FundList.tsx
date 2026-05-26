import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { fundsApi } from '../api/client';
import { Search, Filter, ChevronLeft, ChevronRight } from 'lucide-react';

const FUND_TYPES: Record<string, string> = {
  stock: '股票型', mixed: '混合型', bond: '债券型', index: '指数型',
  fof: 'FOF', money_market: '货币型', qdii: 'QDII',
};

const TYPE_BADGES: Record<string, string> = {
  stock: 'bg-blue-100 text-blue-700',
  mixed: 'bg-purple-100 text-purple-700',
  bond: 'bg-green-100 text-green-700',
  index: 'bg-cyan-100 text-cyan-700',
  fof: 'bg-orange-100 text-orange-700',
  money_market: 'bg-gray-100 text-gray-700',
  qdii: 'bg-pink-100 text-pink-700',
};

const RISK_BADGES: Record<string, string> = {
  low: 'bg-green-50 text-green-600',
  medium: 'bg-yellow-50 text-yellow-600',
  high: 'bg-red-50 text-red-600',
};

const RISK_LABELS: Record<string, string> = {
  low: '低风险', medium: '中风险', high: '高风险',
};

const PAGE_SIZES = [20, 50, 100];

export default function FundList() {
  const navigate = useNavigate();
  const [funds, setFunds] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('');
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params: any = { skip: page * pageSize, limit: pageSize };
      if (typeFilter) params.type = typeFilter;
      if (search) params.q = search;
      const res = await fundsApi.list(params);
      setFunds(res.data);
      setTotal(res.total);
    } catch {
      setError('加载基金列表失败');
    } finally {
      setLoading(false);
    }
  }, [typeFilter, search, page, pageSize]);

  useEffect(() => { load(); }, [load]);

  // Reset page when filters change
  const handleTypeFilter = (t: string) => {
    setTypeFilter(t);
    setPage(0);
  };

  const handleSearch = () => {
    setSearch(searchInput);
    setPage(0);
  };

  const handleClearSearch = () => {
    setSearchInput('');
    setSearch('');
    setPage(0);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">基金列表</h1>
          <p className="text-gray-500 mt-1">全市场公募基金 · 共 {total.toLocaleString()} 只</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="搜索基金代码或名称..."
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            className="input-field pl-9 pr-10"
          />
          {search ? (
            <button
              onClick={handleClearSearch}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs px-2 py-1 rounded bg-gray-100 text-gray-500 font-medium hover:bg-gray-200"
            >
              清除
            </button>
          ) : searchInput !== search && (
            <button
              onClick={handleSearch}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs px-2 py-1 rounded bg-primary-100 text-primary-600 font-medium hover:bg-primary-200"
            >
              搜索
            </button>
          )}
        </div>
        <div className="flex items-center gap-1 overflow-x-auto">
          <button
            onClick={() => handleTypeFilter('')}
            className={`px-3 py-1.5 text-xs font-medium rounded-full whitespace-nowrap transition-colors ${!typeFilter ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}
          >
            全部
          </button>
          {Object.entries(FUND_TYPES).map(([k, v]) => (
            <button
              key={k}
              onClick={() => handleTypeFilter(k)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full whitespace-nowrap transition-colors ${typeFilter === k ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-400 hover:text-red-600">&times;</button>
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden p-0">
        {loading ? (
          <div className="flex items-center justify-center h-48"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" /></div>
        ) : funds.length === 0 ? (
          <div className="text-center py-12">
            <Filter size={36} className="mx-auto text-gray-300 mb-2" />
            <p className="text-gray-400">未找到匹配的基金</p>
            <button onClick={() => { setSearch(''); setSearchInput(''); setTypeFilter(''); setPage(0); }} className="text-sm text-primary-600 hover:underline mt-2">清除筛选</button>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b bg-gray-50 text-left text-sm text-gray-500">
                <th className="px-4 py-3 font-medium">代码</th>
                <th className="px-4 py-3 font-medium">名称</th>
                <th className="px-4 py-3 font-medium">类型</th>
                <th className="px-4 py-3 font-medium">规模</th>
                <th className="px-4 py-3 font-medium">风险等级</th>
                <th className="px-4 py-3 font-medium">基金公司</th>
              </tr>
            </thead>
            <tbody>
              {funds.map(f => (
                <tr key={f.code} className="border-b last:border-0 hover:bg-gray-50 cursor-pointer transition-colors" onClick={() => navigate(`/funds/${f.code}`)}>
                  <td className="px-4 py-3 text-sm font-mono text-primary-600">{f.code}</td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-800 max-w-[240px] truncate">{f.name}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_BADGES[f.type] || 'bg-gray-100 text-gray-600'}`}>
                      {FUND_TYPES[f.type] || f.type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{f.fund_size ? `${(f.fund_size / 1e8).toFixed(2)}亿` : '--'}</td>
                  <td className="px-4 py-3">
                    {f.risk_level ? (
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${RISK_BADGES[f.risk_level] || 'bg-gray-100 text-gray-600'}`}>
                        {RISK_LABELS[f.risk_level] || f.risk_level}
                      </span>
                    ) : '--'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500 max-w-[160px] truncate">{f.company || '--'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <div className="flex items-center gap-3">
            <p className="text-sm text-gray-500">显示 {(page * pageSize) + 1}-{Math.min((page + 1) * pageSize, total)} / 共 {total.toLocaleString()} 只</p>
            <select
              value={pageSize}
              onChange={e => { setPageSize(Number(e.target.value)); setPage(0); }}
              className="text-xs border rounded px-2 py-1 text-gray-600"
            >
              {PAGE_SIZES.map(s => <option key={s} value={s}>每页 {s} 条</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={18} className="text-gray-600" />
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 5) {
                pageNum = i;
              } else if (page < 3) {
                pageNum = i;
              } else if (page > totalPages - 3) {
                pageNum = totalPages - 5 + i;
              } else {
                pageNum = page - 2 + i;
              }
              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                    page === pageNum
                      ? 'bg-primary-100 text-primary-700'
                      : 'text-gray-500 hover:bg-gray-100'
                  }`}
                >
                  {pageNum + 1}
                </button>
              );
            })}
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
