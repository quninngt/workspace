import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { watchlistApi } from '../api/client';
import { Star, Trash2, Plus, ExternalLink } from 'lucide-react';

export default function Watchlist() {
  const navigate = useNavigate();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [fundCode, setFundCode] = useState('');
  const [groupName, setGroupName] = useState('默认');
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const res = await watchlistApi.list();
      setItems(res.data);
    } catch {
      setError('加载自选列表失败');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    setError('');
    try {
      await watchlistApi.add(fundCode, groupName);
      setShowAdd(false);
      setFundCode('');
      load();
    } catch (e: any) {
      setError(e?.response?.data?.detail || '添加失败，请检查基金代码');
    }
  };

  const handleRemove = async (id: number) => {
    try {
      await watchlistApi.remove(id);
      load();
    } catch {
      setError('删除失败');
    }
  };

  // Group by group_name
  const groups = items.reduce<Record<string, any[]>>((acc, item) => {
    const g = item.group_name || '默认';
    if (!acc[g]) acc[g] = [];
    acc[g].push(item);
    return acc;
  }, {});

  const groupNames = Object.keys(groups);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">自选管理</h1>
          <p className="text-gray-500 mt-1">关注你感兴趣的基金</p>
        </div>
        <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> 添加自选
        </button>
      </div>

      {/* Add Modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowAdd(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-sm mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">添加自选基金</h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-gray-500 block mb-1">基金代码</label>
                <input value={fundCode} onChange={e => setFundCode(e.target.value)} className="input-field" placeholder="例如 000001" />
              </div>
              <div>
                <label className="text-sm text-gray-500 block mb-1">分组</label>
                <select value={groupName} onChange={e => setGroupName(e.target.value)} className="input-field">
                  <option value="默认">默认</option>
                  <option value="重点关注">重点关注</option>
                  <option value="观察池">观察池</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowAdd(false)} className="btn-secondary">取消</button>
              <button onClick={handleAdd} disabled={!fundCode} className="btn-primary">添加</button>
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-400 hover:text-red-600">&times;</button>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center h-48"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" /></div>
      ) : items.length === 0 ? (
        <div className="card text-center py-12">
          <Star size={48} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-400">尚未添加自选基金</p>
          <p className="text-gray-400 text-sm mt-1">添加你关注的基金，获取信号和净值动态</p>
        </div>
      ) : (
        <div className="space-y-6">
          {groupNames.map(group => (
            <div key={group} className="card">
              <h2 className="text-lg font-semibold mb-4">{group} ({groups[group].length})</h2>
              <div className="space-y-2">
                {groups[group].map(item => (
                  <div key={item.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50 transition-colors">
                    <div className="flex items-center gap-3">
                      <Star size={16} className="text-yellow-500 fill-yellow-500" />
                      <div>
                        <span className="font-mono text-sm text-primary-600">{item.fund_code}</span>
                        <span className="text-xs text-gray-400 ml-2">{item.group_name}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={() => navigate(`/funds/${item.fund_code}`)} className="p-1.5 hover:bg-primary-50 rounded-lg" title="查看详情">
                        <ExternalLink size={16} className="text-primary-500" />
                      </button>
                      <button onClick={() => handleRemove(item.id)} className="p-1.5 hover:bg-red-50 rounded-lg" title="删除">
                        <Trash2 size={16} className="text-red-400" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
