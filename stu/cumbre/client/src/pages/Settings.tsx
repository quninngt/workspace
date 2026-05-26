import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/client';
import { User, Lock, CheckCircle, AlertCircle } from 'lucide-react';

export default function Settings() {
  const { user } = useAuth();
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);

    if (!currentPw || !newPw || !confirmPw) {
      setMessage({ type: 'error', text: '请填写所有密码字段' });
      return;
    }
    if (newPw !== confirmPw) {
      setMessage({ type: 'error', text: '两次新密码输入不一致' });
      return;
    }
    if (newPw.length < 6) {
      setMessage({ type: 'error', text: '新密码至少6位' });
      return;
    }

    setLoading(true);
    try {
      await authApi.changePassword(currentPw, newPw);
      setMessage({ type: 'success', text: '密码修改成功' });
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
    } catch (err: any) {
      setMessage({ type: 'error', text: err.response?.data?.detail || '修改失败' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800">设置</h1>
        <p className="text-gray-500 mt-1">账户信息和安全设置</p>
      </div>

      {/* Profile Info */}
      <div className="card mb-6">
        <div className="flex items-center gap-2 mb-4">
          <User size={20} className="text-primary-500" />
          <h2 className="text-lg font-semibold">账户信息</h2>
        </div>
        <div className="space-y-3">
          <div className="flex items-center gap-4 py-2 border-b">
            <span className="text-sm text-gray-500 w-20">姓名</span>
            <span className="text-sm font-medium text-gray-800">{user?.name}</span>
          </div>
          <div className="flex items-center gap-4 py-2 border-b">
            <span className="text-sm text-gray-500 w-20">邮箱</span>
            <span className="text-sm font-medium text-gray-800">{user?.email}</span>
          </div>
          <div className="flex items-center gap-4 py-2">
            <span className="text-sm text-gray-500 w-20">用户 ID</span>
            <span className="text-sm font-mono text-gray-400">{user?.id}</span>
          </div>
        </div>
      </div>

      {/* Change Password */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Lock size={20} className="text-primary-500" />
          <h2 className="text-lg font-semibold">修改密码</h2>
        </div>

        <form onSubmit={handleChangePassword} className="space-y-4 max-w-sm">
          {message && (
            <div className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm ${
              message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
            }`}>
              {message.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
              {message.text}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">当前密码</label>
            <input
              type="password"
              value={currentPw}
              onChange={e => setCurrentPw(e.target.value)}
              className="input-field"
              placeholder="输入当前密码"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">新密码</label>
            <input
              type="password"
              value={newPw}
              onChange={e => setNewPw(e.target.value)}
              className="input-field"
              placeholder="至少6位新密码"
              minLength={6}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">确认新密码</label>
            <input
              type="password"
              value={confirmPw}
              onChange={e => setConfirmPw(e.target.value)}
              className="input-field"
              placeholder="再次输入新密码"
            />
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? '修改中...' : '修改密码'}
          </button>
        </form>
      </div>
    </div>
  );
}
