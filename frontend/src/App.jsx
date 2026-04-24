import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceArea, ReferenceLine, AreaChart, Area, ComposedChart,
  ResponsiveContainer
} from 'recharts'

const API = 'http://localhost:8888'

const FACTOR_META = {
  dol:   { label: 'DOL',   color: '#D4A84C', sign: '−', desc: 'Câmbio BRL/USD' },
  di:    { label: 'DI',    color: '#C25C5C', sign: '−', desc: 'Juros futuros BR' },
  vix:   { label: 'VIX',   color: '#7DA3C2', sign: '−', desc: 'Vol S&P 500' },
  dxy:   { label: 'DXY',   color: '#8FA668', sign: '−', desc: 'Dólar index' },
  brent: { label: 'BRENT', color: '#B87DDC', sign: '+', desc: 'Petróleo Brent' },
}

function barToTime(barIdx) {
  const totalMinutes = 10 * 60 + barIdx * 5
  const h = Math.floor(totalMinutes / 60)
  const m = totalMinutes % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

function StatCard({ label, value, unit, sublabel, accent }) {
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 4, padding: '20px 22px', position: 'relative',
    }}>
      <div style={{
        fontFamily: 'var(--font-sans)', fontSize: 10,
        letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-dim)',
      }}>{label}</div>
      <div style={{
        fontFamily: 'var(--font-serif)', fontSize: 44, lineHeight: 1,
        marginTop: 10, color: accent || 'var(--text-primary)', fontWeight: 400,
      }}>
        {value}<span style={{ fontSize: 20, color: 'var(--text-dim)', marginLeft: 4 }}>{unit}</span>
      </div>
      {sublabel && (
        <div style={{
          marginTop: 10, fontFamily: 'var(--font-mono)',
          fontSize: 11, color: 'var(--text-secondary)',
        }}>{sublabel}</div>
      )}
    </div>
  )
}

function FactorBar({ fkey, z, contribution, ret }) {
  const meta = FACTOR_META[fkey]
  if (!meta) return null
  const magnitude = Math.min(Math.abs(z) / 2.5, 1)
  const direction = z >= 0 ? 'right' : 'left'
  return (
    <div style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <div>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 13,
            color: 'var(--text-primary)', fontWeight: 500, marginRight: 8,
          }}>{meta.label}</span>
          <span style={{
            fontFamily: 'var(--font-sans)', fontSize: 10,
            color: 'var(--text-dim)', letterSpacing: '0.05em',
          }}>{meta.sign} · {meta.desc}</span>
        </div>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 13,
          color: z >= 0 ? 'var(--up)' : 'var(--down)', fontWeight: 500,
        }}>{z >= 0 ? '+' : ''}{z.toFixed(2)}σ</span>
      </div>
      <div style={{
        height: 4, background: 'var(--border)', position: 'relative',
        display: 'flex', justifyContent: 'center',
      }}>
        <div style={{
          position: 'absolute', left: '50%', top: -1, bottom: -1,
          width: 1, background: 'var(--text-dim)',
        }} />
        <div style={{
          position: 'absolute',
          [direction === 'right' ? 'left' : 'right']: '50%',
          top: 0, bottom: 0, width: `${magnitude * 50}%`, background: meta.color,
        }} />
      </div>
      <div style={{
        display: 'flex', justifyContent: 'space-between', marginTop: 4,
        fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)',
      }}>
        <span>ret {ret >= 0 ? '+' : ''}{ret.toFixed(3)}%</span>
        <span>contrib {contribution >= 0 ? '+' : ''}{contribution.toFixed(3)}</span>
      </div>
    </div>
  )
}

function LoadingOverlay() {
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(10,10,13,0.85)', display: 'flex',
      alignItems: 'center', justifyContent: 'center', zIndex: 999,
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontFamily: 'var(--font-serif)', fontSize: 36,
          color: 'var(--accent)', marginBottom: 16,
        }}>IRAI</div>
        <div style={{
          fontFamily: 'var(--font-mono)', fontSize: 12,
          color: 'var(--text-secondary)', animation: 'pulse 1.5s infinite',
        }}>carregando dados...</div>
      </div>
    </div>
  )
}

export default function App() {
  const [dates, setDates] = useState([])
  const [selectedDate, setSelectedDate] = useState(null)
  const [series, setSeries] = useState([])
  const [summary, setSummary] = useState(null)
  const [currentBar, setCurrentBar] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Carregar datas disponíveis
  useEffect(() => {
    fetch(`${API}/api/irai/dates`)
      .then(r => r.json())
      .then(data => {
        setDates(data.dates || [])
        if (data.dates && data.dates.length > 0) {
          setSelectedDate(data.dates[0])
        }
      })
      .catch(e => setError(e.message))
  }, [])

  // Carregar série ao mudar data
  useEffect(() => {
    if (!selectedDate) return
    setLoading(true)
    fetch(`${API}/api/irai/series?session_date=${selectedDate}`)
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          setError(data.error)
          setLoading(false)
          return
        }
        const processed = (data.series || []).map((s, i) => ({
          ...s,
          time: barToTime(s.bar_idx),
          z_dol: s.factors?.dol?.z_score || 0,
          z_di: s.factors?.di?.z_score || 0,
          z_vix: s.factors?.vix?.z_score || 0,
          z_dxy: s.factors?.dxy?.z_score || 0,
          z_brent: s.factors?.brent?.z_score || 0,
          c_dol: s.factors?.dol?.contribution || 0,
          c_di: s.factors?.di?.contribution || 0,
          c_vix: s.factors?.vix?.contribution || 0,
          c_dxy: s.factors?.dxy?.contribution || 0,
          c_brent: s.factors?.brent?.contribution || 0,
        }))
        setSeries(processed)
        setSummary(data.summary)
        setCurrentBar(processed.length - 1)
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [selectedDate])

  const now = series[currentBar] || null
  const visible = series.slice(0, currentBar + 1)

  const verdictColor = now
    ? now.p_up > 60 ? 'var(--up)' : now.p_up < 40 ? 'var(--down)' : 'var(--text-secondary)'
    : 'var(--text-secondary)'

  if (error && !series.length) {
    return (
      <div style={{
        minHeight: '100vh', background: '#0a0a0d', color: '#E8E6E1',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'JetBrains Mono, monospace',
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠</div>
          <div style={{ fontSize: 14, color: '#C25C5C', marginBottom: 8 }}>Erro de conexão</div>
          <div style={{ fontSize: 12, color: '#908A7D' }}>{error}</div>
          <div style={{ fontSize: 11, color: '#5A5549', marginTop: 16 }}>
            Backend rodando em localhost:8888?
          </div>
        </div>
      </div>
    )
  }

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap');
        :root {
          --bg: #0a0a0d; --surface: #121217; --surface-el: #16161c;
          --border: #23232b; --border-light: #2d2d36;
          --text-primary: #E8E6E1; --text-secondary: #908A7D; --text-dim: #5A5549;
          --accent: #D4A84C; --up: #6FB38A; --down: #C25C5C; --neutral: #7A7F8A;
          --font-serif: 'Instrument Serif', Georgia, serif;
          --font-sans: 'Instrument Sans', -apple-system, sans-serif;
          --font-mono: 'JetBrains Mono', ui-monospace, monospace;
        }
        * { box-sizing: border-box; }
        body { margin: 0; background: var(--bg); }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        select { background: var(--surface); color: var(--text-primary); border: 1px solid var(--border);
                 padding: 6px 12px; font-family: var(--font-mono); font-size: 11px; border-radius: 2px;
                 cursor: pointer; }
        input[type=range] { accent-color: #D4A84C; }
      `}</style>

      {loading && <LoadingOverlay />}

      <div style={{
        minHeight: '100vh', background: 'var(--bg)', color: 'var(--text-primary)',
        fontFamily: 'var(--font-sans)', padding: '32px 40px',
      }}>
        {/* Header */}
        <header style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
          borderBottom: '1px solid var(--border)', paddingBottom: 24, marginBottom: 32,
        }}>
          <div>
            <div style={{
              fontSize: 10, letterSpacing: '0.25em', textTransform: 'uppercase',
              color: 'var(--accent)', marginBottom: 8,
            }}>Intraday Risk Appetite Index</div>
            <h1 style={{
              fontFamily: 'var(--font-serif)', fontSize: 52, fontWeight: 400,
              margin: 0, letterSpacing: '-0.02em', lineHeight: 1,
            }}>
              IRAI <span style={{ fontStyle: 'italic', color: 'var(--text-dim)' }}>/ IBOV</span>
            </h1>
            <div style={{
              marginTop: 12, fontSize: 12, color: 'var(--text-secondary)',
              fontFamily: 'var(--font-mono)',
            }}>B3 · 10:00 → 17:55 BRT · 5 fatores cross-asset · barras M5</div>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{
              fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.1em',
              textTransform: 'uppercase',
            }}>sessão</span>
            <select value={selectedDate || ''} onChange={e => setSelectedDate(e.target.value)}>
              {dates.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
        </header>

        {now && (
          <>
            {/* Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
              <StatCard
                label="P(↑ fechamento)"
                value={now.p_up.toFixed(1)} unit="%"
                sublabel={`score composto ${now.score >= 0 ? '+' : ''}${now.score.toFixed(3)}`}
                accent={verdictColor}
              />
              <StatCard
                label="Regime atual"
                value={now.verdict.split(' ')[0]} unit=""
                sublabel={now.verdict.includes(' ') ? now.verdict.split(' ').slice(1).join(' ') : 'leitura cross-asset'}
                accent={verdictColor}
              />
              <StatCard
                label="Horário sessão"
                value={now.time} unit=""
                sublabel={`barra ${currentBar + 1} / ${series.length}`}
              />
              <StatCard
                label="WIN retorno"
                value={(now.win_return >= 0 ? '+' : '') + now.win_return.toFixed(2)} unit="%"
                sublabel={`${now.win_open?.toFixed(0) || '—'} → ${now.win_current?.toFixed(0) || '—'}`}
                accent={now.win_return >= 0 ? 'var(--up)' : 'var(--down)'}
              />
            </div>

            {/* Main chart + sidebar */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16, marginBottom: 24 }}>
              <div style={{
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: 4, padding: 20,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-dim)' }}>
                      Rastro de probabilidade de alta
                    </div>
                    <div style={{ fontFamily: 'var(--font-serif)', fontSize: 22, marginTop: 4 }}>
                      <span style={{ fontStyle: 'italic', color: 'var(--text-secondary)' }}>P<sub>up</sub>(t)</span> ao longo do dia
                    </div>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>
                    banda 40–60% = indeciso
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={280}>
                  <ComposedChart data={visible} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="pUpFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#D4A84C" stopOpacity={0.25} />
                        <stop offset="100%" stopColor="#D4A84C" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#1f1f26" vertical={false} />
                    <XAxis dataKey="time" tick={{ fill: '#5A5549', fontSize: 10, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" interval={11} />
                    <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fill: '#5A5549', fontSize: 10, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" tickFormatter={v => `${v}%`} />
                    <ReferenceArea y1={40} y2={60} fill="#23232b" fillOpacity={0.4} />
                    <ReferenceLine y={50} stroke="#3a3a44" strokeDasharray="3 3" />
                    <Tooltip
                      contentStyle={{ background: '#16161c', border: '1px solid #2d2d36', borderRadius: 2, fontFamily: 'JetBrains Mono', fontSize: 11 }}
                      labelStyle={{ color: '#908A7D' }}
                      formatter={(v) => [`${Number(v).toFixed(1)}%`, 'P(↑)']}
                    />
                    <Area type="monotone" dataKey="p_up" stroke="none" fill="url(#pUpFill)" />
                    <Line type="monotone" dataKey="p_up" stroke="#D4A84C" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* Sidebar: factors */}
              <div style={{
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: 4, padding: 20,
              }}>
                <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>
                  Z-scores intraday
                </div>
                <div style={{ fontFamily: 'var(--font-serif)', fontSize: 18, marginBottom: 16, color: 'var(--text-secondary)' }}>
                  <span style={{ fontStyle: 'italic' }}>zᵢ(t)</span> normalizado por vol
                </div>

                {Object.entries(FACTOR_META).map(([key]) => {
                  const f = now.factors?.[key]
                  if (!f) return null
                  return (
                    <FactorBar
                      key={key} fkey={key}
                      z={f.z_score} contribution={f.contribution} ret={f.ret}
                    />
                  )
                })}

                <div style={{
                  marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border-light)',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                }}>
                  <span style={{ fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-dim)' }}>Score composto</span>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 18,
                    color: now.score >= 0 ? 'var(--up)' : 'var(--down)',
                  }}>
                    {now.score >= 0 ? '+' : ''}{now.score.toFixed(3)}
                  </span>
                </div>
              </div>
            </div>

            {/* Contributions + WIN chart */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
              <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4, padding: 20 }}>
                <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-dim)' }}>
                  Contribuições por fator
                </div>
                <div style={{ fontFamily: 'var(--font-serif)', fontSize: 18, marginBottom: 16, color: 'var(--text-secondary)' }}>
                  quem está <span style={{ fontStyle: 'italic' }}>puxando</span> o score
                </div>
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart data={visible} stackOffset="sign" margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="#1f1f26" vertical={false} />
                    <XAxis dataKey="time" tick={{ fill: '#5A5549', fontSize: 9, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" interval={15} />
                    <YAxis tick={{ fill: '#5A5549', fontSize: 9, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" />
                    <ReferenceLine y={0} stroke="#3a3a44" />
                    <Tooltip contentStyle={{ background: '#16161c', border: '1px solid #2d2d36', borderRadius: 2, fontFamily: 'JetBrains Mono', fontSize: 11 }} labelStyle={{ color: '#908A7D' }} />
                    {Object.entries(FACTOR_META).map(([key, m]) => (
                      <Area key={key} type="monotone" dataKey={`c_${key}`} stackId="1" stroke={m.color} fill={m.color} fillOpacity={0.7} isAnimationActive={false} />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
                <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
                  {Object.entries(FACTOR_META).map(([k, m]) => (
                    <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                      <span style={{ width: 10, height: 10, background: m.color, display: 'inline-block' }} />
                      {m.label}
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4, padding: 20 }}>
                <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-dim)' }}>
                  Validação visual
                </div>
                <div style={{ fontFamily: 'var(--font-serif)', fontSize: 18, marginBottom: 16, color: 'var(--text-secondary)' }}>
                  WIN <span style={{ fontStyle: 'italic' }}>real</span> vs P<sub>up</sub>
                </div>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={visible} margin={{ top: 5, right: 25, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="#1f1f26" vertical={false} />
                    <XAxis dataKey="time" tick={{ fill: '#5A5549', fontSize: 9, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" interval={15} />
                    <YAxis yAxisId="left" tick={{ fill: '#5A5549', fontSize: 9, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" tickFormatter={v => `${Number(v).toFixed(1)}%`} />
                    <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tick={{ fill: '#5A5549', fontSize: 9, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" tickFormatter={v => `${v}%`} />
                    <ReferenceLine yAxisId="left" y={0} stroke="#3a3a44" />
                    <Tooltip contentStyle={{ background: '#16161c', border: '1px solid #2d2d36', borderRadius: 2, fontFamily: 'JetBrains Mono', fontSize: 11 }} labelStyle={{ color: '#908A7D' }} />
                    <Line yAxisId="left" type="monotone" dataKey="win_return" stroke="#E8E6E1" strokeWidth={1.5} dot={false} name="WIN %" isAnimationActive={false} />
                    <Line yAxisId="right" type="monotone" dataKey="p_up" stroke="#D4A84C" strokeWidth={1} strokeDasharray="3 2" dot={false} name="P(↑) %" isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
                <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
                  linha contínua: WIN real · tracejado: IRAI
                </div>
              </div>
            </div>

            {/* Time slider */}
            <div style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 4, padding: '16px 20px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <span style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-dim)' }}>
                  Scrub · reproduzir sessão
                </span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
                  {now.time}
                </span>
              </div>
              <input
                type="range" min={0} max={series.length - 1} value={currentBar}
                onChange={e => setCurrentBar(Number(e.target.value))}
                style={{ width: '100%' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)' }}>
                <span>10:00</span><span>12:00</span><span>14:00</span><span>16:00</span><span>17:55</span>
              </div>
            </div>

            {/* Footer */}
            <div style={{
              marginTop: 32, paddingTop: 20, borderTop: '1px solid var(--border)',
              fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', lineHeight: 1.6,
            }}>
              <span style={{ color: 'var(--text-secondary)' }}>método:</span> zᵢ(t) = retᵢ(t) / (σᵢ · √t) · S(t) = Σ wᵢ·zᵢ(t) · P<sub>up</sub>(t) = σ(α·S + intercept)
              <span style={{ marginLeft: 16, color: 'var(--text-secondary)' }}>calibração M5:</span> R²=0.46 · acc=67.5% · α=1.4154
            </div>
          </>
        )}
      </div>
    </>
  )
}
