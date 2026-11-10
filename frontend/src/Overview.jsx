import { useState, useEffect } from 'react'
import { calculateConviction } from './utils/signalAnalyzer'
import { isHonestUi, describeZ, describeNowcast } from './utils/honesty'
import { PineDownloadButton } from './components/PineDownloadModal'

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

  @keyframes badgeBlink {
    0% { opacity: 1; }
    50% { opacity: 0.3; }
    100% { opacity: 1; }
  }
  .badge-blink { animation: badgeBlink 1.5s infinite ease-in-out; }

  /* Health Modal */
  .health-modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 1000; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px); }
  .health-modal { background: #0F172A; border: 1px solid #334155; border-radius: 12px; padding: 24px; min-width: 380px; max-width: 500px; box-shadow: 0 20px 60px rgba(0,0,0,0.5); }
  .health-row { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 6px; margin-bottom: 4px; font-family: var(--font-mono); font-size: 11px; }
  .health-row:hover { background: rgba(255,255,255,0.03); }
  .health-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .health-btn { background: none; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; cursor: pointer; display: flex; align-items: center; gap: 4px; font-family: var(--font-mono); font-size: 9px; transition: all 0.2s; }
  .health-btn:hover { background: #1E293B; border-color: #475569; }

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
    .health-modal { min-width: unset; margin: 16px; }
  }
`
const isLocalhost = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
const FIREBASE_URL = (import.meta.env.DEV || isLocalhost) ? null : import.meta.env.VITE_FIREBASE_URL
const API = FIREBASE_URL ? null : 'http://localhost:8888'

function Sparkline({ data, width = '100%', height = 24 }) {
  if (!data || data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const viewBoxWidth = 185

  const makePoints = (pts) => {
    if (!pts || pts.length < 2) return ''
    return pts.map((v, i) => {
      const x = (i / (pts.length - 1)) * viewBoxWidth
      const y = height - ((v - min) / range) * (height - 4) - 2
      return `${x},${y}`
    }).join(' ')
  }

  const points = makePoints(data)

  return (
    <svg width={width} height={height} viewBox={`0 0 ${viewBoxWidth} ${height}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      {points && (
        <polyline
          fill="none"
          stroke="#60A5FA"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
      )}
    </svg>
  )
}

const COMPONENT_LABELS = {
  'source:tickmill': { label: 'Tickmill', icon: 'ðŸŒ' },
  'source:br': { label: 'B3 (XP)', icon: 'ðŸ‡§ðŸ‡·' },
  'source:axi': { label: 'Axi ETFs', icon: 'ðŸ“Š' },
  'firebase': { label: 'Firebase Sync', icon: 'ðŸ”¥' },
  'service:api': { label: 'API Server', icon: 'ðŸ–¥ï¸' },
  'service:collector': { label: 'Collector', icon: 'âš™ï¸' },
  'processes': { label: 'Processos', icon: 'âš™ï¸' },
  // Firebase RTDB sanitiza ':' para '_' nas chaves
  'source_tickmill': { label: 'Tickmill', icon: 'ðŸŒ' },
  'source_br': { label: 'B3 (XP)', icon: 'ðŸ‡§ðŸ‡·' },
  'source_axi': { label: 'Axi ETFs', icon: 'ðŸ“Š' },
  'service_api': { label: 'API Server', icon: 'ðŸ–¥ï¸' },
  'service_collector': { label: 'Collector', icon: 'âš™ï¸' },
}

function HealthModal({ data, onClose }) {
  if (!data) return null
  const components = data.components || []
  const allOk = data.healthy
  const ageMin = data.age_seconds ? Math.round(data.age_seconds / 60) : '?'

  return (
    <div className="health-modal-overlay" onClick={onClose}>
      <div className="health-modal" onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: 18, color: allOk ? '#4ADE80' : '#F87171', fontWeight: 500 }}>
              {allOk ? 'Sistema Saudavel' : 'Problemas Detectados'}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: '#64748B', marginTop: 2 }}>
              Atualizado ha {ageMin} min{data.stale ? ' (DEFASADO)' : ''}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: '#64748B', fontSize: 18,
            cursor: 'pointer', padding: '4px 8px', lineHeight: 1
          }}>x</button>
        </div>

        {components.map((c, i) => {
          const meta = COMPONENT_LABELS[c.endpoint] || { label: c.endpoint, icon: '?' }
          return (
            <div key={i} className="health-row">
              <span className="health-dot" style={{ background: c.healthy ? '#4ADE80' : '#F87171' }} />
              <span style={{ color: '#94A3B8', minWidth: 24 }}>{meta.icon}</span>
              <span style={{ color: '#C8C8D4', flex: 1 }}>{meta.label}</span>
              <span style={{ color: c.healthy ? '#4ADE80' : '#F87171', textAlign: 'right', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {c.message}
              </span>
            </div>
          )
        })}

        {components.length === 0 && (
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#475569', textAlign: 'center', padding: 20 }}>
            Watchdog ainda nao executou
          </div>
        )}
      </div>
    </div>
  )
}

export default function Overview({ onSelectTarget }) {
  const [targets, setTargets] = useState([])
  const [overview, setOverview] = useState([])
  const [loading, setLoading] = useState(true)
  const [health, setHealth] = useState(null)
  const [showHealthModal, setShowHealthModal] = useState(false)
  const [watchdogData, setWatchdogData] = useState(null)

  useEffect(() => {
    async function fetchHealth() {
      try {
        if (FIREBASE_URL) {
          const baseUrl = FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '')
          const res = await fetch(`${baseUrl}/health.json`)
          const data = await res.json()
          setHealth(data)
        } else {
          const res = await fetch(`${API}/api/health`)
          const data = await res.json()
          setHealth(data)
        }
      } catch (e) {
        console.error("Error fetching system health:", e)
      }
    }
    fetchHealth()
    const timer = setInterval(fetchHealth, 30000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    async function load() {
      try {
        if (FIREBASE_URL) {
          const baseUrl = FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '')
          const [tRes, oRes] = await Promise.all([
            fetch(`${baseUrl}/targets.json`),
            fetch(`${baseUrl}/overview.json`),
          ])
          const tData = await tRes.json()
          const oData = await oRes.json()
          setTargets(tData?.targets || [])
          setOverview(oData?.targets || [])
        } else {
          const [tRes, oRes] = await Promise.all([
            fetch(`${API}/api/irai/targets`),
            fetch(`${API}/api/irai/overview?version=v2`),
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
      // Firebase: poll every 120s
      pollTimer = setInterval(async () => {
        if (!mounted) return
        try {
          const baseUrl = FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '')
          const [tRes, oRes] = await Promise.all([
            fetch(`${baseUrl}/targets.json`),
            fetch(`${baseUrl}/overview.json`),
          ])
          const tData = await tRes.json()
          const oData = await oRes.json()
          setTargets(tData?.targets || [])
          setOverview(oData?.targets || [])
        } catch (e) { console.error('Overview poll error:', e) }
      }, 120_000)
    } else {
      // Local: simple HTTP polling every 20s
      pollTimer = setInterval(async () => {
        if (!mounted) return
        try {
          const [oRes] = await Promise.all([
            fetch(`${API}/api/irai/overview?version=v2`),
          ])
          const oData = await oRes.json()
          setOverview(oData.targets || [])
        } catch (e) { console.error('Overview poll error:', e) }
      }, 20_000)
    }
    
    return () => {
      mounted = false
      if (pollTimer) clearInterval(pollTimer)
    }
  }, [])

  // Merge targets + overview data (deduplicated by target symbol)
  const uniqueCardsMap = new Map();
  targets.forEach(t => {
    if (t.target && !uniqueCardsMap.has(t.target)) {
      const live = overview.find(o => o.target === t.target) || {};
      uniqueCardsMap.set(t.target, { ...t, ...live });
    }
  });
  const cards = Array.from(uniqueCardsMap.values());

  const ASSET_ORDER = [
    "WIN$N",
    "WDO$N",
    "BTCUSD",
    "USTEC",
    "US500",
    "US30",
    "US2000",
    "DE40",
    "JP225",
    "CHINA50",
    "XAUUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY"
  ];

  const calibrated = cards
    .filter(c => c.calibrated)
    .sort((a, b) => {
      const indexA = ASSET_ORDER.indexOf(a.target);
      const indexB = ASSET_ORDER.indexOf(b.target);
      const valA = indexA === -1 ? 999 : indexA;
      const valB = indexB === -1 ? 999 : indexB;
      return valA - valB;
    });

  const pending = cards
    .filter(c => !c.calibrated)
    .sort((a, b) => {
      const indexA = ASSET_ORDER.indexOf(a.target);
      const indexB = ASSET_ORDER.indexOf(b.target);
      const valA = indexA === -1 ? 999 : indexA;
      const valB = indexB === -1 ? 999 : indexB;
      return valA - valB;
    });

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
            INTRADAY RISK APPETITE INDEX Â· {calibrated.length} MODELOS ATIVOS
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* B3 Status */}
          {health ? (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: '#1E293B', border: '1px solid #334155',
              padding: '4px 8px', borderRadius: '4px',
              fontFamily: 'var(--font-mono)', fontSize: 9,
              color: health.b3_status === 'OK' ? '#4ADE80' : health.b3_status === 'DELAYED' ? '#EF4444' : '#94A3B8'
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: health.b3_status === 'OK' ? '#4ADE80' : health.b3_status === 'DELAYED' ? '#EF4444' : '#94A3B8',
                animation: health.b3_status === 'OK' ? 'pulse 2s infinite' : 'none'
              }} />
              B3: {health.b3_status === 'OK' ? `REAL-TIME` : health.b3_status === 'DELAYED' ? `ATRASADO (${health.b3_delay_min}m)` : 'FECHADO'}
              {health.b3_last_bar && <span style={{ color: '#64748B', marginLeft: 2 }}>({health.b3_last_bar.substring(11, 16)})</span>}
            </div>
          ) : (
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: '#64748B' }}>Conectando B3...</div>
          )}

          {/* Global Status */}
          {health ? (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: '#1E293B', border: '1px solid #334155',
              padding: '4px 8px', borderRadius: '4px',
              fontFamily: 'var(--font-mono)', fontSize: 9,
              color: health.global_status === 'OK' ? '#4ADE80' : health.global_status === 'DELAYED' ? '#EF4444' : '#94A3B8'
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: health.global_status === 'OK' ? '#4ADE80' : health.global_status === 'DELAYED' ? '#EF4444' : '#94A3B8',
                animation: health.global_status === 'OK' ? 'pulse 2s infinite' : 'none'
              }} />
              GLOBAL: {health.global_status === 'OK' ? `REAL-TIME` : health.global_status === 'DELAYED' ? `ATRASADO (${health.global_delay_min}m)` : 'FECHADO'}
              {health.global_last_bar && <span style={{ color: '#64748B', marginLeft: 2 }}>({health.global_last_bar.substring(11, 16)})</span>}
            </div>
          ) : (
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: '#64748B' }}>Conectando Global...</div>
          )}

          {/* Health Status Button */}
          <button
            className="health-btn"
            onClick={async () => {
              try {
                const url = FIREBASE_URL
                  ? `${FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '')}/health_watchdog.json`
                  : `${API}/api/health/watchdog`
                const res = await fetch(url)
                const data = await res.json()
                setWatchdogData(data)
                setShowHealthModal(true)
              } catch (e) {
                setWatchdogData({ available: false, healthy: false, components: [], stale: true, age_seconds: 0 })
                setShowHealthModal(true)
              }
            }}
            style={{
              color: watchdogData?.healthy === true ? '#4ADE80' : watchdogData?.healthy === false ? '#F87171' : '#94A3B8',
            }}
          >
            <span style={{ fontSize: 12 }}>&#9829;</span>
            HEALTH
          </button>

          {/* Pine Script Download Button (protegido por senha validada no servidor) */}
          <PineDownloadButton firebaseUrl={FIREBASE_URL} />
        </div>
      </header>

      {/* Health Status Modal */}
      {showHealthModal && <HealthModal data={watchdogData} onClose={() => setShowHealthModal(false)} />}

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
            Aguardando dados Â· {pending.length} ativos
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
        <span>IRAI Multi-Asset v2.0 Â· Cross-asset macro factor models</span>
        <span>Push em tempo real ativo</span>
      </div>
    </div>
  )
}


function AssetCard({ card, onClick }) {
  const pUp = card.p_up != null ? card.p_up : 50
  // Fase 17: com forecast_ui 'on'/'nowcast_only' o card fica descritivo (sem acc in-sample, sem COMPRA/VENDA do z)
  const honest = isHonestUi(card.forecast_ui)
  const accuracy = card.accuracy || 80
  const isBuy = pUp >= 60
  const isSell = pUp <= 40

  const directionText = honest ? describeNowcast(pUp).label : (isBuy ? 'ALTA' : isSell ? 'BAIXA' : 'NEUTRO')
  const signalColor = isBuy ? '#4ADE80' : isSell ? '#F87171' : '#64748B'
  const bgColor = isBuy ? 'rgba(74,222,128,0.04)' : isSell ? 'rgba(248,113,113,0.04)' : 'rgba(71,85,105,0.03)'
  const borderColor = isBuy ? 'rgba(74,222,128,0.15)' : isSell ? 'rgba(248,113,113,0.15)' : '#1C1C22'

  const nweUp = card.nwe_slope !== undefined ? card.nwe_slope >= 0 : undefined;
  const isNweDivergentBuy = isBuy && nweUp === false;
  const isNweDivergentSell = isSell && nweUp === true;
  
  const isReturnDivergentBuy = isBuy && card.win_return < 0;
  const isReturnDivergentSell = isSell && card.win_return > 0;
  
  const isNweExhaustionDown = card.nwe_upper_price !== undefined && card.nwe_upper_price !== null && card.win_current !== undefined && card.win_current !== null && card.win_current > card.nwe_upper_price;
  const isNweExhaustionUp = card.nwe_lower_price !== undefined && card.nwe_lower_price !== null && card.win_current !== undefined && card.win_current !== null && card.win_current < card.nwe_lower_price;

  const hasAlert = isReturnDivergentBuy || isReturnDivergentSell;
  const alertClass = hasAlert ? (isBuy ? 'card-alert-green' : 'card-alert-red') : '';

  // ConvicÃ§Ã£o calibrada por Shrinkage (mesmo algoritmo do SignalGauge)
  const { conviction, convLabel, convColor } = calculateConviction(
    pUp,
    honest ? null : accuracy,
    card.is_preview,
    signalColor,
    '#334155'
  );

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
          {/* Direction label â€” large */}
          <div style={{
            fontFamily: 'var(--font-serif)', fontSize: 24,
            color: signalColor, fontWeight: 400, lineHeight: 1,
          }}>{directionText}</div>
          {/* Conviction % */}
          <div style={{ display: 'flex', gap: 12 }}>
            <div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: convColor, marginTop: 4, fontWeight: 600 }}>
                convicÃ§Ã£o {conviction}%
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#2A2A36', marginTop: 2 }}>
                P(â†‘) {pUp.toFixed(0)}%
              </div>
            </div>
          </div>
        </div>

        {/* Indicators Column (D P Z E) */}
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {/* D: DivergÃªncia de Retorno (Cor fixa, sem blink local) */}
          <div title="DivergÃªncia de Retorno %" style={{
            width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 4, fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 600,
            background: (isReturnDivergentBuy || isReturnDivergentSell) ? (isReturnDivergentBuy ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)') : 'rgba(148,163,184,0.05)',
            color: (isReturnDivergentBuy || isReturnDivergentSell) ? (isReturnDivergentBuy ? '#4ADE80' : '#F87171') : '#475569',
            border: `1px solid ${(isReturnDivergentBuy || isReturnDivergentSell) ? (isReturnDivergentBuy ? 'rgba(74,222,128,0.4)' : 'rgba(248,113,113,0.4)') : 'rgba(148,163,184,0.1)'}`
          }}>D</div>

          {/* P: Pullback / NWE Divergence (Blink) */}
          <div title="Pullback / DivergÃªncia Gauss" className={(isNweDivergentBuy || isNweDivergentSell) ? 'badge-blink' : ''} style={{
            width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 4, fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 600,
            background: (isNweDivergentBuy || isNweDivergentSell) ? (isNweDivergentBuy ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)') : 'rgba(148,163,184,0.05)',
            color: (isNweDivergentBuy || isNweDivergentSell) ? (isNweDivergentBuy ? '#4ADE80' : '#F87171') : '#475569',
            border: `1px solid ${(isNweDivergentBuy || isNweDivergentSell) ? (isNweDivergentBuy ? 'rgba(74,222,128,0.4)' : 'rgba(248,113,113,0.4)') : 'rgba(148,163,184,0.1)'}`
          }}>P</div>

          {/* Z: Z-Score (Blink) */}
          <div title="Z-Score" className={card.price_diverges ? 'badge-blink' : ''} style={{
            width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 4, fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 600,
            background: card.price_diverges ? (isBuy ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)') : 'rgba(148,163,184,0.05)',
            color: card.price_diverges ? (isBuy ? '#4ADE80' : '#F87171') : '#475569',
            border: `1px solid ${card.price_diverges ? (isBuy ? 'rgba(74,222,128,0.4)' : 'rgba(248,113,113,0.4)') : 'rgba(148,163,184,0.1)'}`
          }}>Z</div>

          {/* E: ExaustÃ£o NWE (Blink) */}
          <div title="ExaustÃ£o Gauss" className={(isNweExhaustionUp || isNweExhaustionDown) ? 'badge-blink' : ''} style={{
            width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 4, fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 600,
            background: (isNweExhaustionUp || isNweExhaustionDown) ? (isNweExhaustionUp ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)') : 'rgba(148,163,184,0.05)',
            color: (isNweExhaustionUp || isNweExhaustionDown) ? (isNweExhaustionUp ? '#4ADE80' : '#F87171') : '#475569',
            border: `1px solid ${(isNweExhaustionUp || isNweExhaustionDown) ? (isNweExhaustionUp ? 'rgba(74,222,128,0.4)' : 'rgba(248,113,113,0.4)') : 'rgba(148,163,184,0.1)'}`
          }}>E</div>
        </div>
      </div>

      {/* Mini Indicators Row */}
      {(() => {
        const pz = card.pair_z;
        let pzSignal = 'NEUTRO';
        let pzColor = '#64748B';
        if (pz != null) {
          if (pz <= -2.0) { pzSignal = 'COMPRA'; pzColor = '#10B981'; }
          else if (pz < -0.5) { pzSignal = 'COMPRA L.'; pzColor = '#4ADE80'; }
          else if (pz >= 2.0) { pzSignal = 'VENDA'; pzColor = '#EF4444'; }
          else if (pz > 0.5) { pzSignal = 'VENDA L.'; pzColor = '#F87171'; }
        }

        const pfz = card.pair_fixed_z;
        let pfzSignal = 'NEUTRO';
        let pfzColor = '#64748B';
        if (pfz != null) {
          if (pfz <= -2.0) { pfzSignal = 'COMPRA'; pfzColor = '#10B981'; }
          else if (pfz < -0.5) { pfzSignal = 'COMPRA L.'; pfzColor = '#4ADE80'; }
          else if (pfz >= 2.0) { pfzSignal = 'VENDA'; pfzColor = '#EF4444'; }
          else if (pfz > 0.5) { pfzSignal = 'VENDA L.'; pfzColor = '#F87171'; }
        }

        const rz = card.price_diverge_z;
        let rzSignal = 'NEUTRO';
        let rzColor = '#64748B';
        if (rz != null) {
          if (rz <= -2.0) { rzSignal = 'COMPRA'; rzColor = '#10B981'; }
          else if (rz < -0.5) { rzSignal = 'COMPRA L.'; rzColor = '#4ADE80'; }
          else if (rz >= 2.0) { rzSignal = 'VENDA'; rzColor = '#EF4444'; }
          else if (rz > 0.5) { rzSignal = 'VENDA L.'; rzColor = '#F87171'; }
        }

        if (honest) {
          ({ label: pzSignal, color: pzColor } = describeZ(pz, { short: true }));
          ({ label: pfzSignal, color: pfzColor } = describeZ(pfz, { short: true }));
          ({ label: rzSignal, color: rzColor } = describeZ(rz, { short: true }));
        }

        return (
          <div style={{
            marginTop: 8, padding: '4px 6px', borderRadius: 4, background: 'rgba(28,28,34,0.3)',
            border: '1px solid #1C1C22', display: 'flex', flexDirection: 'column', gap: 3
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 8 }}>
              <span style={{ color: '#64748B' }}>{honest ? 'NOWCAST:' : 'PD RASTRO:'}</span>
              <span style={{ color: signalColor, fontWeight: 600 }}>{pUp.toFixed(1)}% ({directionText})</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 8 }}>
              <span style={{ color: '#64748B' }}>Z SPREAD:</span>
              <span style={{ color: pzColor, fontWeight: 600 }}>
                {pz != null ? `${pz >= 0 ? '+' : ''}${pz.toFixed(2)}` : 'N/A'} ({pzSignal})
              </span>
            </div>
            {(card.target === 'WIN$N' || card.target === 'WDO$N' || pfz != null) && (
              <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 8 }}>
                <span style={{ color: '#64748B' }}>{card.target === 'WIN$N' ? 'Z WDO:' : (card.target === 'WDO$N' ? 'Z WIN:' : 'Z PAR FIXO:')}</span>
                <span style={{ color: pfzColor, fontWeight: 600 }}>
                  {pfz != null ? `${pfz >= 0 ? '+' : ''}${pfz.toFixed(2)}` : 'N/A'} ({pfzSignal})
                </span>
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 8 }}>
              <span style={{ color: '#64748B' }}>Z RASTRO:</span>
              <span style={{ color: rzColor, fontWeight: 600 }}>
                {rz != null ? `${rz >= 0 ? '+' : ''}${rz.toFixed(2)}` : 'N/A'} ({rzSignal})
              </span>
            </div>
          </div>
        );
      })()}

      {/* Footer: acc + coint + bars */}
      <div style={{
        marginTop: 8, fontFamily: 'var(--font-mono)', fontSize: 7,
        color: '#475569', display: 'flex', justifyContent: 'space-between',
      }}>
        {honest ? (
          <span>leitura do dia (nowcast)</span>
        ) : (
          <>
            <span>{`acc ${accuracy ? accuracy.toFixed(0) : '0'}%`} Â· p-val: {card.johansen_p_value != null ? Number(card.johansen_p_value).toFixed(3) : '1.000'}</span>
            <span style={{ color: card.is_cointegrated !== false ? '#4ADE80' : '#F87171', fontWeight: 600 }}>
              {card.is_cointegrated !== false ? 'coint âœ“' : 'coint âœ—'}
            </span>
          </>
        )}
        <span>{card.bars || 0} barras</span>
      </div>

      {/* Sparkline (DinÃ¢mico) */}
      <div className="sparkline-wrapper">
        <Sparkline data={card.sparkline} />
      </div>
    </div>
  )
}

