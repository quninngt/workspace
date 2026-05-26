import { NavLink } from 'react-router-dom';
import { LayoutDashboard, List, BarChart3, PlayCircle, Edit3, Briefcase, Star, Settings as SettingsIcon, Wrench, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import clsx from 'clsx';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '市场总览', end: true },
  { to: '/funds', icon: List, label: '基金列表' },
  { to: '/auto', icon: PlayCircle, label: '自动跟投' },
  { to: '/manual', icon: Edit3, label: '执行清单' },
  { to: '/portfolio', icon: Briefcase, label: '手动组合' },
  { to: '/watchlist', icon: Star, label: '自选管理' },
  { to: '/tools', icon: Wrench, label: '工具箱' },
  { to: '/backtest', icon: BarChart3, label: '历史回测' },
  { to: '/settings', icon: SettingsIcon, label: '设置' },
];

export default function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="w-64 bg-white border-r border-gray-200 min-h-screen flex flex-col shrink-0">
      <div className="p-5 border-b">
        <h1 className="text-xl font-bold text-primary-600">Cumbre</h1>
        <p className="text-xs text-gray-500 mt-1">基金智投跟投平台</p>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => clsx(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              isActive ? 'bg-primary-50 text-primary-700' : 'text-gray-600 hover:bg-gray-50'
            )}
          >
            <item.icon size={20} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center text-primary-600 font-semibold text-sm">
            {user?.name?.[0]}
          </div>
          <div className="text-sm">
            <p className="font-medium text-gray-700">{user?.name}</p>
            <p className="text-gray-400 text-xs">{user?.email}</p>
          </div>
        </div>
        <button onClick={logout} className="flex items-center gap-2 text-sm text-gray-500 hover:text-red-500 transition-colors w-full">
          <LogOut size={16} /> 退出登录
        </button>
      </div>
    </aside>
  );
}
