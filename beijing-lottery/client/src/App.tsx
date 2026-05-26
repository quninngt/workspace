import { useState, useEffect, useCallback } from 'react'
import { XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'

const API = '/api/lottery'

function api(path: string, opts?: RequestInit) {
  return fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  }).then(r => r.json())
}

// ── Types ──
interface DrawResult {
  attempt: number
  won: boolean
  chances: number
  probability_pct: number
  total_pool_chances: number
  pool_size: number
  quota_per_draw: number
}

interface Profile {
  name: string
  total_attempts: number
  base_chances: number
  probability_pct: number
  is_winner: boolean
  won_at_attempt: number | null
  records: DrawResult[]
  simulation_params: Record<string, number>
}

interface TrendPoint {
  attempt: number
  probability_pct: number
  chances: number
  won: boolean
}

// ── Helpers ──
function attemptToYearLabel(attempt: number): string {
  const year = Math.floor((attempt - 1) / 2) + 1
  const half = (attempt - 1) % 2 === 0 ? '上' : '下'
  return `${year}年${half}`
}

// ── Main Component ──
export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [trend, setTrend] = useState<TrendPoint[]>([])
  const [loading, setLoading] = useState(false)
  const [batchYears, setBatchYears] = useState(3)
  const [message, setMessage] = useState('')
  const [showHistory, setShowHistory] = useState(false)

  const load = useCallback(async () => {
    const p = await api('/profile') as Profile
    setProfile(p)
    const t = await api('/probability-trend') as { trend: TrendPoint[] }
    setTrend(t.trend || [])
  }, [])

  useEffect(() => { load() }, [load])

  const handleDraw = async () => {
    if (profile?.is_winner) return
    setLoading(true)
    setMessage('')
    try {
      const r = await api('/draw', { method: 'POST' }) as any
      if (r.won) setMessage(`🎉 中签！第 ${r.attempt} 期 (${attemptToYearLabel(r.attempt)})`)
      else setMessage(`❌ 第 ${r.attempt} 期未中 (概率 ${r.probability_pct}%)`)
      await load()
    } catch { setMessage('请求失败') }
    setLoading(false)
  }

  const handleBatch = async () => {
    if (profile?.is_winner) return
    setLoading(true)
    setMessage('')
    try {
      const r = await api(`/draw-batch?years=${batchYears}`, { method: 'POST' }) as any
      if (r.won) setMessage(`🎉 快进 ${batchYears} 年，第 ${r.won_at_attempt} 期中签！`)
      else setMessage(`⏳ 快进 ${batchYears} 年 (${r.draws_attempted} 期)，未中签 (基数=${r.current_profile.base_chances})`)
      await load()
    } catch { setMessage('请求失败') }
    setLoading(false)
  }

  const handleReset = async () => {
    await api('/reset', { method: 'POST' })
    setMessage('已重置，重新开始')
    await load()
  }

  const pct = profile?.probability_pct ?? 0
  const pctFormatted = pct.toFixed(3)
  const isWinner = profile?.is_winner ?? false
  const records = profile?.records ?? []
  const totalAttempts = profile?.total_attempts ?? 0
  const baseChances = profile?.base_chances ?? 1
  const params = profile?.simulation_params ?? {}
  const poolSize = (params.pool_size ?? 2600000).toLocaleString()
  const quota = (params.quota_per_draw ?? 19000).toLocaleString()
  const interval = params.chance_interval ?? 2
  const drawsPerYear = params.draws_per_year ?? 2

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: '16px' }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <div style={{ fontSize: 40, marginBottom: 4 }}>🚗</div>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: '#dc2626' }}>北京摇号模拟器</h1>
        <p style={{ fontSize: 13, color: '#9ca3af', marginTop: 4 }}>
          模拟个人小客车指标摇号 • 一年两期 • 阶梯基数递增
        </p>
      </div>

      {/* Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="stat-value" style={{ color: isWinner ? '#16a34a' : '#dc2626' }}>
            {isWinner ? '🎉' : totalAttempts}
          </div>
          <div className="stat-label">{isWinner ? '已中签！' : '累计摇号次数'}</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="stat-value" style={{ color: '#2563eb' }}>{baseChances}</div>
          <div className="stat-label">阶梯基数</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="stat-value" style={{ color: pct > 1 ? '#16a34a' : '#d97706' }}>{pctFormatted}%</div>
          <div className="stat-label">本期概率</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="stat-value" style={{ color: '#7c3aed' }}>
            {isWinner ? attemptToYearLabel(profile!.won_at_attempt!) : '—'}
          </div>
          <div className="stat-label">{isWinner ? '中签期次' : '等待中'}</div>
        </div>
      </div>

      {/* Big Draw Button */}
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <button
          onClick={handleDraw}
          disabled={loading || isWinner}
          className="btn btn-primary"
          style={{
            width: '100%',
            padding: '20px',
            fontSize: 20,
            borderRadius: 16,
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {loading ? '摇号中...' : isWinner ? '✅ 已中签' : '🔮 摇一期'}
        </button>
        {!isWinner && (
          <p style={{ fontSize: 12, color: '#9ca3af', marginTop: 8 }}>
            本期概率 {pctFormatted}% • 基数 {baseChances} 个机会
          </p>
        )}
      </div>

      {/* Batch Controls */}
      {!isWinner && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#4b5563', marginBottom: 8 }}>
            快进模式（一次模拟 N 年，每年 {drawsPerYear} 期）
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="number"
              value={batchYears}
              onChange={e => setBatchYears(Math.max(1, Math.min(60, Number(e.target.value))))}
              style={{
                flex: 1, padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db',
                fontSize: 14, outline: 'none',
              }}
              min={1} max={60}
            />
            <button onClick={handleBatch} disabled={loading} className="btn btn-gold" style={{ padding: '8px 20px' }}>
              快进
            </button>
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            {[1, 3, 5, 10].map(n => (
              <button key={n} onClick={() => setBatchYears(n)}
                style={{
                  padding: '4px 12px', borderRadius: 6, border: '1px solid #e5e7eb',
                  fontSize: 12, background: batchYears === n ? '#fef2f2' : 'white',
                  color: batchYears === n ? '#dc2626' : '#6b7280', cursor: 'pointer',
                }}
              >{n}年</button>
            ))}
          </div>
        </div>
      )}

      {/* Message */}
      {message && (
        <div className="card" style={{ marginBottom: 16, textAlign: 'center', background: '#fffbeb', border: '1px solid #fde68a' }}>
          <span style={{ fontSize: 14, color: '#92400e' }}>{message}</span>
        </div>
      )}

      {/* Probability Trend Chart */}
      {trend.length > 1 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#4b5563' }}>概率变化趋势</span>
            <span className={`badge ${isWinner ? 'badge-green' : 'badge-amber'}`}>
              {isWinner
                ? `第${profile?.won_at_attempt}期 (${attemptToYearLabel(profile!.won_at_attempt!)})中签`
                : `${totalAttempts}期未中`}
            </span>
          </div>
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="colorProb" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#dc2626" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="attempt"
                  tick={{ fontSize: 10 }}
                  stroke="#d1d5db"
                  tickFormatter={(v: number) => `${Math.floor((v - 1) / 2) + 1}年`}
                />
                <YAxis tick={{ fontSize: 10 }} stroke="#d1d5db" tickFormatter={(v: number) => `${v.toFixed(2)}%`} />
                <Tooltip
                  formatter={(value: number) => [`${value.toFixed(3)}%`, '概率']}
                  labelFormatter={(label: number) => `第${label}期 (${attemptToYearLabel(label)})`}
                />
                <Area type="monotone" dataKey="probability_pct" stroke="#dc2626" fill="url(#colorProb)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          {trend.length > 0 && (
            <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11, color: '#9ca3af' }}>
              <span>开始: {trend[0]?.probability_pct.toFixed(3)}%</span>
              <span>当前: {trend[trend.length - 1]?.probability_pct.toFixed(3)}%</span>
            </div>
          )}
        </div>
      )}

      {/* History Toggle */}
      {records.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <button
            onClick={() => setShowHistory(!showHistory)}
            style={{
              width: '100%', background: 'none', border: 'none',
              fontSize: 13, fontWeight: 600, color: '#4b5563',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              cursor: 'pointer', padding: 0,
            }}
          >
            <span>摇号记录 ({records.length})</span>
            <span style={{ fontSize: 16 }}>{showHistory ? '▲' : '▼'}</span>
          </button>
          {showHistory && (
            <div style={{ marginTop: 12, maxHeight: 300, overflow: 'auto' }}>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ color: '#9ca3af', borderBottom: '1px solid #e5e7eb', textAlign: 'left' }}>
                    <th style={{ padding: '6px 8px' }}>期次</th>
                    <th style={{ padding: '6px 8px' }}>时间</th>
                    <th style={{ padding: '6px 8px' }}>结果</th>
                    <th style={{ padding: '6px 8px' }}>基数</th>
                    <th style={{ padding: '6px 8px' }}>概率</th>
                  </tr>
                </thead>
                <tbody>
                  {[...records].reverse().slice(0, 100).map(r => (
                    <tr key={r.attempt} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '6px 8px', color: '#6b7280' }}>{r.attempt}</td>
                      <td style={{ padding: '6px 8px', color: '#6b7280', fontSize: 11 }}>
                        {attemptToYearLabel(r.attempt)}
                      </td>
                      <td style={{ padding: '6px 8px' }}>
                        {r.won ? <span style={{ color: '#16a34a', fontWeight: 600 }}>🎉 中签</span> : '❌'}
                      </td>
                      <td style={{ padding: '6px 8px', color: '#6b7280' }}>{r.chances}</td>
                      <td style={{ padding: '6px 8px', color: '#6b7280' }}>{r.probability_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Reset + Info */}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
        <button onClick={handleReset} className="btn btn-secondary" style={{ padding: '10px 20px', fontSize: 13 }}>
          🔄 重置重来
        </button>
      </div>

      {/* Footer */}
      <div style={{ textAlign: 'center', marginTop: 24, fontSize: 11, color: '#d1d5db' }}>
        模拟参数：池 {poolSize} 人 | 每期 {quota} 指标 | 每 {interval} 次不中基数+1 | 每年 {drawsPerYear} 期
      </div>
    </div>
  )
}
