import { useState, useEffect, useCallback } from 'react'

// ── Types ──

interface ServiceStatus {
  id: string
  name: string
  description: string
  category: string
  status: 'running' | 'partial' | 'stopped'
  backend: { port: number; alive: boolean }
  frontend: { port: number; alive: boolean }
  web_url: string | null
  tunnel: string | null
}

// ── Icons ──

const STATUS_ICONS: Record<string, string> = {
  running: '🟢',
  partial: '🟡',
  stopped: '🔴',
}

const CATEGORY_ICONS: Record<string, string> = {
  '模拟器': '🎲',
  '金融': '💰',
  '系统': '⚙️',
}

// ── Component ──

export default function App() {
  const [services, setServices] = useState<ServiceStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [actionMsg, setActionMsg] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const fetchServices = useCallback(async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true)
    try {
      const res = await fetch('/api/services')
      const data = await res.json()
      setServices(data.services || [])
    } catch {
      // Silent fail
    } finally {
      setLoading(false)
      if (showRefresh) setTimeout(() => setRefreshing(false), 600)
    }
  }, [])

  useEffect(() => {
    fetchServices()
    const timer = setInterval(() => fetchServices(), 8000)
    return () => clearInterval(timer)
  }, [fetchServices])

  const handleAction = async (id: string, action: 'start' | 'stop' | 'restart') => {
    setActionMsg('')
    try {
      const res = await fetch(`/api/services/${id}/${action}`, { method: 'POST' })
      const data = await res.json()
      setActionMsg(`✅ ${action} ${data.backend_started || data.frontend_started ? '成功' : '完成'}`)
      setTimeout(() => fetchServices(), 1500)
      setTimeout(() => setActionMsg(''), 3000)
    } catch {
      setActionMsg('❌ 操作失败')
    }
  }

  // ── Render ──

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="header-left">
            <span className="logo">📊</span>
            <div>
              <h1 className="title">服务管理门户</h1>
              <p className="subtitle">统一管理所有运行中的服务</p>
            </div>
          </div>
          <button
            className={`refresh-btn ${refreshing ? 'spinning' : ''}`}
            onClick={() => fetchServices(true)}
            title="刷新状态"
          >
            🔄
          </button>
        </div>
      </header>

      <main className="main">
        {/* Status Summary */}
        {!loading && (
          <div className="summary">
            <div className="summary-item">
              <span className="summary-icon">🟢</span>
              <span>{services.filter(s => s.status === 'running').length} 运行中</span>
            </div>
            <div className="summary-item">
              <span className="summary-icon">🟡</span>
              <span>{services.filter(s => s.status === 'partial').length} 部分运行</span>
            </div>
            <div className="summary-item">
              <span className="summary-icon">🔴</span>
              <span>{services.filter(s => s.status === 'stopped').length} 已停止</span>
            </div>
          </div>
        )}

        {/* Action Message */}
        {actionMsg && <div className="toast">{actionMsg}</div>}

        {/* Loading */}
        {loading && (
          <div className="loading">
            <div className="spinner"></div>
            <p>查询服务状态...</p>
          </div>
        )}

        {/* Service Cards */}
        {!loading && (
          <div className="grid">
            {services.map(s => (
              <div key={s.id} className={`card card-${s.status}`}>
                {/* Card Header */}
                <div className="card-header">
                  <div className="card-title-row">
                    <span className="card-icon">{CATEGORY_ICONS[s.category] || '📦'}</span>
                    <div>
                      <h2 className="card-title">{s.name}</h2>
                      <p className="card-desc">{s.description}</p>
                    </div>
                  </div>
                  <span className="status-dot" title={s.status}>
                    {STATUS_ICONS[s.status]}
                  </span>
                </div>

                {/* Status Detail */}
                <div className="card-details">
                  <div className="detail-row">
                    <span className="detail-label">后端</span>
                    <span className={`detail-value ${s.backend.alive ? 'alive' : 'dead'}`}>
                      {s.backend.alive ? '✅ 运行中' : '❌ 已停止'} (:{s.backend.port})
                    </span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">前端</span>
                    <span className={`detail-value ${s.frontend.alive ? 'alive' : 'dead'}`}>
                      {s.frontend.alive ? '✅ 运行中' : '❌ 已停止'} (:{s.frontend.port})
                    </span>
                  </div>
                  {s.tunnel && (
                    <div className="detail-row">
                      <span className="detail-label">隧道</span>
                      <a
                        href={s.tunnel}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="tunnel-link"
                      >
                        🔗 打开
                      </a>
                    </div>
                  )}
                  {!s.tunnel && s.id === 'portal' && (
                    <div className="detail-row">
                      <span className="detail-label">隧道</span>
                      <span className="detail-value dead">等待配置</span>
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="card-actions">
                  {s.status !== 'running' && (
                    <button
                      className="btn btn-start"
                      onClick={() => handleAction(s.id, 'start')}
                    >
                      ▶️ 启动
                    </button>
                  )}
                  {s.status !== 'stopped' && (
                    <>
                      <button
                        className="btn btn-stop"
                        onClick={() => handleAction(s.id, 'stop')}
                      >
                        ⏹️ 停止
                      </button>
                      <button
                        className="btn btn-restart"
                        onClick={() => handleAction(s.id, 'restart')}
                      >
                        🔄 重启
                      </button>
                    </>
                  )}
                  {s.web_url && s.status !== 'stopped' && (
                    <a
                      href={s.web_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-open"
                    >
                      🌐 打开
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="footer">
          <p>每 8 秒自动刷新 · 服务管理门户 v1.0</p>
        </div>
      </main>
    </div>
  )
}
