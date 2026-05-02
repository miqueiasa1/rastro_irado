import { useState, useEffect } from 'react'

const OVERVIEW_STYLES = `
  @keyframes borderGlowGreen {
    0%, 100% { box-shadow: 0 0 5px rgba(74,222,128,0.2), inset 0 0 5px rgba(74,222,128,0.05); border-color: rgba(74,222,128,0.4); }
    50% { box-shadow: 0 0 15px rgba(74,222,128,0.6), inset 0 0 10px rgba(74,222,128,0.1); border-color: rgba(74,222,128,0.8); }
  }
  @keyframes borderGlowRed {
    0%, 100% { box-shadow: 0 0 5px rgba(248,113,113,0.2), inset 0 0 5px rgba(248,113,113,0.05); border-color: rgba(248,113,113,0.4); }
    50% { box-shadow: 0 0 15px rgba(248,113,113,0.6), inset 0 0 10px rgba(248,113,113,0.1); border-color: rgba(248,113,113,0.8); }
  }
  .card-alert-green { animation: borderGlowGreen 2s infinite ease-in-out; }
  .card-alert-red { animation: borderGlowRed 2s infinite ease-in-out; }

  /* Mobile Responsive Overrides */
  .overview-container { padding: 24px 32px; max-width: 1400px; margin: 0 auto; font-family: var(--font-sans); color: #C8C8D4; }
  .overview-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 24px; }
  .overview-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
  .overview-grid-pending { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 8px; }
  .asset-card { padding: 14px 16px 12px; transition: all 0.2s ease; cursor: pointer; position: relative; overflow: hidden; }
  .sparkline-wrapper { margin-top: 10px; width: 100%; }
  
  @media (max-width: 768px) {
    .overview-container { padding: 16px 12px !important; }
    .overview-header { flex-direction: column; align-items: flex-start !important; gap: 16px; }
    .overview-grid { grid-template-columns: 1fr !important; }
    .overview-grid-pending { grid-template-columns: 1fr !important; }
    .asset-card { padding: 12px !important; }
    .sparkline-wrapper { margin-top: 16px !important; }
  }
`
const FIREBASE_URL = import.meta.env.VITE_FIREBASE_URL
const API = FIREBASE_URL ? null : 'http://localhost:8888'

function Sparkline({ data, width = '100%', height = 24 }) {
  if (!data || data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const viewBoxWidth = 185
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * viewBoxWidth
    const y = height - ((v - min) / range) * (height - 4) - 2
    return `${x},${y}`
  }).join(' ')

  const last = data[data.length - 1]
  const color = last >= 60 ? '#4ADE80' : last <= 40 ? '#F87171' : '#94A3B8'

  return (
    <svg width={width} height={height} viewBox={`0 0 ${viewBoxWidth} ${height}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  )
}

export default function Overview({ onSelectTarget }) {
  const [targets, setTargets] = useState([])
  const [overview, setOverview] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        if (FIREBASE_URL) {
          const url = FIREBASE_URL.endsWith('.json') ? FIREBASE_URL : `${FIREBASE_URL.replace(/\/$/, '')}/db.json`
          const res = await fetch(url)
          const db = await res.json()
          setTargets(db?.targets?.targets || [])
          setOverview(db?.overview?.targets || [])
        } else {
          const [tRes, oRes] = await Promise.all([
            fetch(`${API}/api/irai/targets`),
            fetch(`${API}/api/irai/overview`),
          ])
          const tData = await tRes.json()
          const oData = await oRes.json()
          setTargets(tData.targets || [])
          setOverview(oData.targets || [])
        }
      } catch (e) {
        console.error('Overview load error:', e)
      } finally {
        setLoading(false)
      }
    }
    load()
    
    let mounted = true
    let pollTimer = null
    
    if (FIREBASE_URL) {
      // Firebase: poll every 60s (SSE unreliable for large payloads)
      pollTimer = setInterval(async () => {
        if (!mounted) return
        try {
          const url = FIREBASE_URL.endsWith('.json') ? FIREBASE_URL : `${FIREBASE_URL.replace(/\/$/, '')}/db.json`
          const res = await fetch(url)
          const db = await res.json()
          setTargets(db?.targets?.targets || [])
          setOverview(db?.overview?.targets || [])
        } catch (e) { console.error('Overview poll error:', e) }
      }, 60_000)
    } else {
      // Local: simple HTTP polling every 60s
      pollTimer = setInterval(async () => {
        if (!mounted) return
        try {
          const [oRes] = await Promise.all([
            fetch(`${API}/api/irai/overview`),
          ])
          const oData = await oRes.json()
          setOverview(oData.targets || [])
        } catch (e) { console.error('Overview poll error:', e) }
      }, 60_000)
    }
    
    return () => {
      mounted = false
      if (pollTimer) clearInterval(pollTimer)
    }
  }, [])

  // Merge targets + overview data
  const cards = targets.map(t => {
    const live = overview.find(o => o.target === t.target) || {}
    return { ...t, ...live }
  })

  const calibrated = cards.filter(c => c.calibrated)
  const pending = cards.filter(c => !c.calibrated)

  if (loading) {
    return (
      <div style={{
        height: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', color: '#64748B',
        fontFamily: 'var(--font-mono)', fontSize: 14,
      }}>
        Carregando modelos...
      </div>
    )
  }

  return (
    <div className="overview-container">
      <style>{OVERVIEW_STYLES}</style>
      {/* Header */}
      <header className="overview-header">
        <div>
          <div style={{
            fontFamily: 'var(--font-serif)', fontSize: 28,
            fontWeight: 500, color: '#C9A227', lineHeight: 1,
            letterSpacing: '0.04em',
          }}>
            IRAI <span style={{ color: '#3A3A4A', fontWeight: 300 }}>Multi-Asset</span>
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 10,
            color: '#3A3A4A', marginTop: 4, letterSpacing: '0.12em',
          }}>
            INTRADAY RISK APPETITE INDEX · {calibrated.length} MODELOS ATIVOS
          </div>
        </div>
        <div style={{
          fontFamily: 'var(--font-mono)', fontSize: 10,
          color: '#4ADE80', display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%', background: '#4ADE80',
            animation: 'pulse 2s infinite',
          }} />
          LIVE
        </div>
      </header>

      {/* Active Models Grid */}
      <div className="overview-grid">
        {calibrated.map(card => (
          <AssetCard key={card.target} card={card} onClick={() => onSelectTarget?.(card.target)} />
        ))}
      </div>

      {/* Pending Models */}
      {pending.length > 0 && (
        <>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 9,
            color: '#334155', marginTop: 24, marginBottom: 8,
            letterSpacing: '0.15em', textTransform: 'uppercase',
          }}>
            Aguardando dados · {pending.length} ativos
          </div>
          <div className="overview-grid-pending">
            {pending.map(card => (
              <div key={card.target} style={{
                background: 'rgba(15,23,42,0.5)',
                border: '1px solid #1E293B',
                borderRadius: 6, padding: '10px 14px',
                opacity: 0.5,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 16 }}>{card.icon}</span>
                  <div>
                    <div style={{
                      fontFamily: 'var(--font-mono)', fontSize: 11,
                      color: '#64748B', fontWeight: 600,
                    }}>{card.display_name}</div>
                    <div style={{
                      fontFamily: 'var(--font-mono)', fontSize: 8,
                      color: '#334155',
                    }}>{card.session_hours}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Footer */}
      <div style={{
        marginTop: 24, paddingTop: 12, borderTop: '1px solid #1E293B',
        fontFamily: 'var(--font-mono)', fontSize: 9, color: '#1E293B',
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span>IRAI Multi-Asset v2.0 · Cross-asset macro factor models</span>
        <span>Push em tempo real ativo</span>
      </div>
    </div>
  )
}


function AssetCard({ card, onClick }) {
  const pUp = card.p_up || 50
  const accuracy = card.accuracy || 80
  const isBuy = pUp >= 60
  const isSell = pUp <= 40

  const directionText = isBuy ? 'ALTA' : isSell ? 'BAIXA' : 'NEUTRO'
  const signalColor = isBuy ? '#4ADE80' : isSell ? '#F87171' : '#64748B'
  const bgColor = isBuy ? 'rgba(74,222,128,0.04)' : isSell ? 'rgba(248,113,113,0.04)' : 'rgba(71,85,105,0.03)'
  const borderColor = isBuy ? 'rgba(74,222,128,0.15)' : isSell ? 'rgba(248,113,113,0.15)' : '#1C1C22'

  const nweUp = card.nwe_slope !== undefined ? card.nwe_slope >= 0 : undefined;
  const isNweDivergentBuy = isBuy && nweUp === false;
  const isNweDivergentSell = isSell && nweUp === true;
  
  const hasAlert = card.price_diverges || isNweDivergentBuy || isNweDivergentSell;
  const alertClass = hasAlert ? (isBuy ? 'card-alert-green' : 'card-alert-red') : '';

  // Convicção calibrada por Shrinkage (mesmo algoritmo do SignalGauge)
  const acc = Math.min(Math.max(accuracy, 50), 100)
  const shrinkFactor = (2 * acc / 100) - 1
  const pShrunk = 50 + (pUp - 50) * shrinkFactor
  const conviction = Math.round(Math.abs(pShrunk - 50) * 2)
  const maxConviction = Math.round((acc - 50) * 2)
  const convRatio = maxConviction > 0 ? conviction / maxConviction : 0
  const convLabel = card.is_preview ? 'pré-mercado' : (convRatio >= 0.55 ? 'forte' : convRatio >= 0.25 ? 'moderada' : 'fraca')
  const convColor = card.is_preview ? '#EAB308' : (convRatio >= 0.55 ? signalColor : convRatio >= 0.25 ? '#C9A227' : '#334155')

  const ret = card.win_return || 0

  return (
    <div
      onClick={onClick}
      className={`asset-card ${alertClass}`}
      style={{
        background: bgColor,
        border: `1px solid ${borderColor}`,
        borderRadius: 8,
      }}
      onMouseEnter={e => {
        e.currentTarget.style.transform = 'translateY(-2px)'
        e.currentTarget.style.borderColor = signalColor
        e.currentTarget.style.boxShadow = `0 4px 20px ${signalColor}15`
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.borderColor = borderColor
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      {/* Top row: icon + name + signal badge */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 18, lineHeight: 1, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{card.icon}</span>
          <div>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 12,
              fontWeight: 700, color: '#C8C8D4', lineHeight: 1,
            }}>{card.display_name}</div>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 7,
              color: '#2A2A36', marginTop: 1,
            }}>{card.target}</div>
          </div>
        </div>
        {/* Conviction badge top-right */}
        <div style={{
          fontFamily: 'var(--font-mono)', fontSize: 8, fontWeight: 700,
          color: convColor, letterSpacing: '0.04em',
          padding: '2px 6px', borderRadius: 3,
          background: `${convColor}18`,
          border: `1px solid ${convColor}33`,
        }}>
          {convLabel}
        </div>
      </div>

      {/* Direction + conviction (main body) */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'flex-end', marginTop: 10,
      }}>
        <div>
          {/* Direction label — large */}
          <div style={{
            fontFamily: 'var(--font-serif)', fontSize: 24,
            color: signalColor, fontWeight: 400, lineHeight: 1,
          }}>{directionText}</div>
          {/* Conviction % */}
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 10,
            color: convColor, marginTop: 4, fontWeight: 600,
          }}>
            convicção {conviction}%
          </div>
          {/* Raw P(↑) — small, secondary */}
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 8,
            color: '#2A2A36', marginTop: 2,
          }}>P(↑) {pUp.toFixed(0)}%</div>
        </div>

        {/* Indicators Column */}
        <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-end' }}>
          {/* Z-SCORE SIGNAL */}
          <div style={{
            background: card.price_diverges ? (isBuy ? 'rgba(74,222,128,0.12)' : 'rgba(248,113,113,0.12)') : 'rgba(148,163,184,0.08)',
            color: card.price_diverges ? (isBuy ? '#4ADE80' : '#F87171') : '#64748B',
            padding: '2px 6px', borderRadius: 4, fontSize: 8,
            fontFamily: 'var(--font-mono)', border: `1px solid ${card.price_diverges ? (isBuy ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)') : 'rgba(148,163,184,0.1)'}`
          }}>
            {card.price_diverges ? (isBuy ? '🟢 Z-SCORE' : '🔴 Z-SCORE') : '✓ Z-SCORE'}
          </div>

          {/* NWE SIGNAL */}
          {(() => {
            if (card.nwe_slope === undefined) return null;
            const nweUp = card.nwe_slope >= 0;
            const isDivergentBuy = isBuy && !nweUp;
            const isDivergentSell = isSell && nweUp;
            
            let bg = 'rgba(148,163,184,0.08)';
            let color = '#64748B';
            let border = 'rgba(148,163,184,0.1)';
            let text = '✓ NWE';
            
            if (isDivergentBuy) {
              bg = 'rgba(74,222,128,0.12)'; color = '#4ADE80'; border = 'rgba(74,222,128,0.2)'; text = '🟢 NWE COMPRA';
            } else if (isDivergentSell) {
              bg = 'rgba(248,113,113,0.12)'; color = '#F87171'; border = 'rgba(248,113,113,0.2)'; text = '🔴 NWE VENDA';
            }

            return (
              <div style={{
                background: bg, color: color,
                padding: '2px 6px', borderRadius: 4, fontSize: 8,
                fontFamily: 'var(--font-mono)', border: `1px solid ${border}`
              }}>
                {text}
              </div>
            );
          })()}
        </div>
      </div>

      {/* Sparkline */}
      <div className="sparkline-wrapper">
        <Sparkline data={card.sparkline} width="100%" height={24} />
      </div>

      {/* Footer: acc + bars */}
      <div style={{
        marginTop: 8, fontFamily: 'var(--font-mono)', fontSize: 7,
        color: '#1E1E28', display: 'flex', justifyContent: 'space-between',
      }}>
        <span>acc {accuracy.toFixed(0)}%</span>
        <span>{card.bars || 0} barras</span>
      </div>
    </div>
  )
}

