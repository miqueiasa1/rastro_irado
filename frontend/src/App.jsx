import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceArea, ReferenceLine, Area, ComposedChart,
  ResponsiveContainer, Bar, Cell, Brush
} from 'recharts'
import Overview from './Overview'

const FIREBASE_URL = import.meta.env.VITE_FIREBASE_URL
const API = FIREBASE_URL ? null : 'http://localhost:8888'
const WS_URL = FIREBASE_URL ? null : 'ws://localhost:8888/ws/irai'

// Mapa cosmético de labels para fatores conhecidos
const FACTOR_DISPLAY = {
  win: { label: 'WIN', icon: 'BR' }, dol: { label: 'DÓLAR', icon: 'US' },
  di1: { label: 'JUROS', icon: 'BR' }, dxy: { label: 'DXY', icon: 'DX' },
  brent: { label: 'PETRÓLEO', icon: 'PT' }, china50: { label: 'CHINA50', icon: 'CN' },
  usdmxn: { label: 'USDMXN', icon: 'MX' }, vix: { label: 'VIX', icon: 'VX' },
  btcusd: { label: 'BITCOIN', icon: '₿' }, us500: { label: 'S&P 500', icon: 'US' },
  us30: { label: 'DOW 30', icon: 'DJ' }, ustec: { label: 'NASDAQ', icon: 'NQ' },
  xauusd: { label: 'OURO', icon: 'GL' }, eurusd: { label: 'EUR/USD', icon: 'EU' },
  gbpusd: { label: 'GBP/USD', icon: 'GB' }, usdjpy: { label: 'USD/JPY', icon: 'JP' },
  audusd: { label: 'AUD/USD', icon: 'AU' }, usdcad: { label: 'USD/CAD', icon: 'CA' },
  usdchf: { label: 'USD/CHF', icon: 'CH' }, nzdusd: { label: 'NZD/USD', icon: 'NZ' },
  eurgbp: { label: 'EUR/GBP', icon: 'EG' }, eurchf: { label: 'EUR/CHF', icon: 'EC' },
  eurjpy: { label: 'EUR/JPY', icon: 'EJ' }, gbpjpy: { label: 'GBP/JPY', icon: 'GJ' },
  euraud: { label: 'EUR/AUD', icon: 'EA' },
}

// Gera meta de fator dinamicamente a partir da key
function getFactorMeta(fkey) {
  const known = FACTOR_DISPLAY[fkey]
  if (known) return { label: known.label, icon: known.icon, desc: known.label }
  return { label: fkey.toUpperCase(), icon: '📊', desc: fkey }
}



/* ── Big Gauge ────────────────────────────────────── */
function SignalGauge({ pUp, verdict, score, winReturn, flowConfirms, cumDeltaNorm, targetLabel, hasFlow = true, accuracy = 80, recentPUp = [], priceDiverges, nweUp, isPreview }) {
  const isBuy = pUp >= 60
  const isSell = pUp <= 40

  const signalText = isBuy ? 'ALTA' : isSell ? 'BAIXA' : 'NEUTRO'
  const signalColor = isBuy ? '#4ADE80' : isSell ? '#F87171' : '#94A3B8'
  const signalBg = isBuy ? 'rgba(74,222,128,0.08)' : isSell ? 'rgba(248,113,113,0.08)' : 'rgba(148,163,184,0.05)'

  // ── Convicção calibrada por Shrinkage ──────────────────────────────
  // P_shrunk = 50 + (P_raw - 50) × (2×acc - 1)
  // Convicção = distância do ponto neutro após calibração, normalizada 0–100%
  const acc = Math.min(Math.max(accuracy, 50), 100) // garante 50–100%
  const shrinkFactor = (2 * acc / 100) - 1           // 0 (acc=50%) … 1 (acc=100%)
  const pShrunk = 50 + (pUp - 50) * shrinkFactor
  const conviction = Math.round(Math.abs(pShrunk - 50) * 2) // 0–max(acc)%

  // Teto de convicção para este modelo: acc=80% → max=60%, acc=91% → max=82%
  // Labels são relativos ao teto — 3 faixas apenas
  //   forte:   convRatio ≥ 55%  →  P(↑) ≥ ~78% num modelo de acc=80%
  //   moderada: convRatio ≥ 25%  →  P(↑) ≥ ~62% num modelo de acc=80%
  //   fraca:   qualquer sinal acima do neutro
  const maxConviction = Math.round((acc - 50) * 2)
  const convRatio = maxConviction > 0 ? conviction / maxConviction : 0

  const convLabel = isPreview ? 'pré-mercado' :
    convRatio >= 0.55 ? 'forte' :
    convRatio >= 0.25 ? 'moderada' : 'fraca'
  const convColor = isPreview ? '#EAB308' :
    convRatio >= 0.55 ? signalColor :
    convRatio >= 0.25 ? '#C9A227' :
    '#475569'

  // ── Estabilidade (últimas 8 barras) ───────────────────────────────
  // Mede quanto o P(↑) variou e se cruzou o neutro (50)
  let stability = 'sem dados'
  let stabilityIcon = '○'
  let stabilityColor = '#334155'
  let stabilityTip = ''

  if (recentPUp.length >= 4) {
    const vals = recentPUp.slice(-8)
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length
    const std = Math.sqrt(vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length)

    // Cruzamento de neutro: alguma barra acima e alguma abaixo de 50
    const hasCross = vals.some(v => v > 50) && vals.some(v => v < 50)

    // Trend: P(↑) nas últimas 4 barras vs. 4 barras anteriores
    const half = Math.floor(vals.length / 2)
    const early = vals.slice(0, half).reduce((a, b) => a + b, 0) / half
    const late  = vals.slice(half).reduce((a, b) => a + b, 0) / (vals.length - half)
    const trending = Math.abs(late - early) > 6  // deslocamento > 6pp entre metades

    if (hasCross || std > 18) {
      stability = 'oscilando'
      stabilityIcon = '⟆'
      stabilityColor = '#FBBF24'
      stabilityTip = `Sinal instável — P(↑) cruzou o neutro nas últimas ${vals.length} barras (σ=${std.toFixed(1)}pp). Aguarde confirmação.`
    } else if (trending && std > 6) {
      stability = 'formando'
      stabilityIcon = '◈'
      stabilityColor = '#60A5FA'
      stabilityTip = `Sinal em formação — ${late > early ? 'ganhando' : 'perdendo'} convicção nas últimas ${vals.length} barras (σ=${std.toFixed(1)}pp).`
    } else if (std <= 6) {
      stability = 'estável'
      stabilityIcon = '▬'
      stabilityColor = '#4ADE80'
      stabilityTip = `Sinal estável — baixa variação nas últimas ${vals.length} barras (σ=${std.toFixed(1)}pp).`
    } else {
      stability = 'variando'
      stabilityIcon = '~'
      stabilityColor = '#94A3B8'
      stabilityTip = `Variação moderada (σ=${std.toFixed(1)}pp).`
    }
  }

  // ── Gauge needle ──────────────────────────────────────────────────
  const angleRad = Math.PI * (1 - pUp / 100)

  return (
    <div className="gauge-container" style={{
      background: signalBg,
      border: `1px solid ${signalColor}22`,
      padding: '14px 28px',
    }}>
      {/* SVG Gauge */}
      <div style={{ position: 'relative', width: 110, height: 62, flexShrink: 0 }}>
        <svg viewBox="0 0 110 62" width="110" height="62">
          <path d="M 8 58 A 48 48 0 0 1 102 58" fill="none" stroke="#1E293B" strokeWidth="6" strokeLinecap="round" />
          <path d="M 8 58 A 48 48 0 0 1 22 20" fill="none" stroke="#F8717133" strokeWidth="6" strokeLinecap="round" />
          <path d="M 88 20 A 48 48 0 0 1 102 58" fill="none" stroke="#4ADE8033" strokeWidth="6" strokeLinecap="round" />
          <line
            x1="55" y1="58"
            x2={55 + 38 * Math.cos(angleRad)}
            y2={58 - 38 * Math.sin(angleRad)}
            stroke={signalColor} strokeWidth="2" strokeLinecap="round"
          />
          <circle cx="55" cy="58" r="3" fill={signalColor} />
          <text x="6" y="56" fill="#F87171" fontSize="7" fontFamily="var(--font-mono)">↓</text>
          <text x="49" y="10" fill="#64748B" fontSize="7" fontFamily="var(--font-mono)">50%</text>
          <text x="96" y="56" fill="#4ADE80" fontSize="7" fontFamily="var(--font-mono)">↑</text>
        </svg>
      </div>

      {/* Signal text */}
      <div className="gauge-left">
        <div style={{
          fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.15em',
          color: '#64748B', textTransform: 'uppercase', marginBottom: 4,
        }}>sinal IRAI</div>
        <div style={{
          fontFamily: 'var(--font-serif)', fontSize: 38, lineHeight: 1,
          color: signalColor, fontWeight: 400,
        }}>{signalText}</div>

        {/* Conviction + stability row */}
        <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {/* Conviction */}
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 11, color: '#64748B',
          }}>
            convicção{' '}
            <span style={{ color: convColor, fontWeight: 600 }}>{conviction}%</span>
            <span style={{ color: '#334155', fontSize: 9 }}> ({convLabel})</span>
          </span>

          {/* Divider */}
          <span style={{ color: '#1E293B', fontSize: 11 }}>·</span>

          {/* Stability badge */}
          <span
            title={stabilityTip}
            style={{
              fontFamily: 'var(--font-mono)', fontSize: 10,
              color: stabilityColor,
              background: `${stabilityColor}18`,
              border: `1px solid ${stabilityColor}33`,
              borderRadius: 4, padding: '1px 7px',
              cursor: 'help',
              letterSpacing: '0.06em',
            }}
          >
            {stabilityIcon} {stability}
          </span>
        </div>

        {/* Raw p_up — secondary, small */}
        <div style={{ marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 9, color: '#334155' }}>
          P(↑) bruto: {pUp.toFixed(1)}% · acc modelo: {accuracy.toFixed(0)}%
        </div>
      </div>

      {/* Target return + flow */}
      <div className="gauge-right">
        <div style={{
          fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.12em',
          color: '#64748B', textTransform: 'uppercase', marginBottom: 3,
        }}>{targetLabel || 'WIN'} agora</div>
        <div style={{
          fontFamily: 'var(--font-serif)', fontSize: 28, lineHeight: 1,
          color: winReturn >= 0 ? '#4ADE80' : '#F87171',
        }}>{winReturn >= 0 ? '+' : ''}{winReturn.toFixed(2)}%</div>
        {/* Z-SCORE SIGNAL */}
        <div style={{
          marginTop: 6, fontFamily: 'var(--font-mono)', fontSize: 9,
          padding: '2px 6px', borderRadius: 4, display: 'inline-block',
          background: priceDiverges ? (isBuy ? 'rgba(74,222,128,0.12)' : 'rgba(248,113,113,0.12)') : 'rgba(148,163,184,0.08)',
          color: priceDiverges ? (isBuy ? '#4ADE80' : '#F87171') : '#64748B',
          border: `1px solid ${priceDiverges ? (isBuy ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)') : 'rgba(148,163,184,0.1)'}`,
        }}>
          {priceDiverges ? (isBuy ? '🟢 COMPRA Z-SCORE' : '🔴 VENDA Z-SCORE') : '✓ Z-SCORE ALINHADO'}
        </div>

        {/* NWE SIGNAL */}
        {(() => {
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
              marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 9,
              padding: '2px 6px', borderRadius: 4, display: 'inline-block',
              background: bg, color: color, border: `1px solid ${border}`,
            }}>
              {text}
            </div>
          );
        })()}
      </div>
    </div>
  )
}

/* ── Factor signal card ──────────────────────────── */
function FactorSignal({ fkey, data }) {
  const meta = getFactorMeta(fkey)
  if (!data) return null

  const z = data.z_score || 0
  const ret = data.ret || 0

  // Para fatores invertidos: z positivo = ruim para IBOV (fator subiu mas é negativo para IBOV)
  // A contribuição já tem o sinal correto
  const contrib = data.contribution || 0
  const isFavorBuy = contrib > 0.02
  const isFavorSell = contrib < -0.02
  const isNeutral = !isFavorBuy && !isFavorSell

  const label = isFavorBuy ? 'COMPRA' : isFavorSell ? 'VENDA' : '—'
  const color = isFavorBuy ? '#4ADE80' : isFavorSell ? '#F87171' : '#475569'
  const bgColor = isFavorBuy ? 'rgba(74,222,128,0.06)' : isFavorSell ? 'rgba(248,113,113,0.06)' : 'rgba(71,85,105,0.04)'
  const borderColor = isFavorBuy ? 'rgba(74,222,128,0.15)' : isFavorSell ? 'rgba(248,113,113,0.15)' : 'rgba(71,85,105,0.1)'

  // Intensity bar width (0–100%)
  const intensity = Math.min(Math.abs(contrib) / 0.5, 1) * 100

  return (
    <div style={{
      background: bgColor, border: `1px solid ${borderColor}`,
      borderRadius: 6, padding: '14px 16px',
      display: 'flex', alignItems: 'center', gap: 12,
      transition: 'all 0.3s ease',
    }}>
      {/* Icon */}
      <div style={{ fontSize: 22, lineHeight: 1, width: 28, textAlign: 'center' }}>{meta.icon}</div>

      {/* Info */}
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600,
            color: '#CBD5E1',
          }}>{meta.label}</span>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600,
            color: color, letterSpacing: '0.05em',
          }}>{label}</span>
        </div>

        {/* Intensity bar */}
        <div style={{
          marginTop: 6, height: 3, background: '#1E293B', borderRadius: 2,
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', top: 0, bottom: 0, left: 0,
            width: `${intensity}%`, background: color,
            borderRadius: 2, transition: 'width 0.5s ease',
          }} />
        </div>

        <div style={{
          marginTop: 4, display: 'flex', justifyContent: 'space-between',
          fontFamily: 'var(--font-mono)', fontSize: 9, color: '#475569',
        }}>
          <span>{meta.desc}</span>
          <span>{ret >= 0 ? '+' : ''}{ret.toFixed(2)}%</span>
        </div>
      </div>
    </div>
  )
}

/* ── Custom tooltip ──────────────────────────────── */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  const pUp = payload.find(p => p.dataKey === 'p_up')?.value
  const winRet = payload.find(p => p.dataKey === 'win_return')?.value
  const isBuy = pUp >= 60
  const isSell = pUp <= 40
  return (
    <div style={{
      background: '#0F172A', border: '1px solid #1E293B', borderRadius: 4,
      padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 11,
    }}>
      <div style={{ color: '#94A3B8', marginBottom: 6 }}>{label}</div>
      <div style={{ color: isBuy ? '#4ADE80' : isSell ? '#F87171' : '#CBD5E1', fontWeight: 600 }}>
        P(↑) = {pUp?.toFixed(1)}%
        <span style={{ marginLeft: 8, fontSize: 10, fontWeight: 400 }}>
          {isBuy ? '▲ COMPRA' : isSell ? '▼ VENDA' : '— NEUTRO'}
        </span>
      </div>
      {winRet != null && (
        <div style={{ color: winRet >= 0 ? '#4ADE80' : '#F87171', marginTop: 2 }}>
          Retorno: {winRet >= 0 ? '+' : ''}{winRet.toFixed(3)}%
        </div>
      )}
    </div>
  )
}

/* ── NWE (Nadaraya-Watson Envelope) ──────────────── */
const NWE_BW = 8;    // bandwidth (kernel width)
const NWE_MULT = 3;  // envelope multiplier

function computeNWE(data) {
  if (!data || data.length < 3) return data;
  const n = data.length;
  const h = NWE_BW;
  const vals = data.map(d => d.win_return || 0);

  // 1) Kernel regression (center line)
  const center = [];
  const WINDOW = 3 * h;  // Beyond 3σ the kernel weight is < 1% — safe to skip
  for (let i = 0; i < n; i++) {
    let sumW = 0, sumY = 0;
    const jStart = Math.max(0, i - WINDOW);
    const jEnd = Math.min(n, i + WINDOW + 1);
    for (let j = jStart; j < jEnd; j++) {
      const w = Math.exp(-Math.pow(i - j, 2) / (2 * h * h));
      sumW += w;
      sumY += w * vals[j];
    }
    center.push(sumY / sumW);
  }

  // 2) Envelope width from MAD of residuals × mult
  const resSorted = vals.map((v, i) => Math.abs(v - center[i])).sort((a, b) => a - b);
  const mad = resSorted[Math.floor(resSorted.length * 0.5)] || 0.001;
  const envWidth = mad * NWE_MULT;

  // 3) Build enriched data with per-bar slope coloring
  //    nwe_up = center value when slope >= 0 (green segments)
  //    nwe_down = center value when slope < 0 (red segments)
  //    At transition points, both are set so lines connect
  return data.map((d, i) => {
    const nwe_center = center[i];
    const nwe_upper = center[i] + envWidth;
    const nwe_lower = center[i] - envWidth;
    const nwe_slope = i > 0 ? center[i] - center[i - 1] : 0;
    const isUp = nwe_slope >= 0;

    // Check if next bar changes direction (transition point)
    const nextSlope = i < n - 1 ? center[i + 1] - center[i] : nwe_slope;
    const isTransition = (nwe_slope >= 0) !== (nextSlope >= 0);
    // Check if previous bar was different direction
    const prevSlope = i > 1 ? center[i - 1] - center[i - 2] : nwe_slope;
    const wasTransition = i > 0 && ((prevSlope >= 0) !== (nwe_slope >= 0));

    return {
      ...d,
      nwe_center,
      nwe_upper,
      nwe_lower,
      nwe_slope,
      // Both series get the value at transition points for continuity
      nwe_up: (isUp || isTransition || wasTransition) ? nwe_center : null,
      nwe_down: (!isUp || isTransition || wasTransition) ? nwe_center : null,
    };
  });
}

/* ── Main App ────────────────────────────────────── */
const REFRESH_INTERVAL = 30_000 // 30 seconds (fallback polling)

export default function App() {
  const [page, setPage] = useState('overview')
  const [dates, setDates] = useState([])
  const [selectedDate, setSelectedDate] = useState(null)
  const [liveMode, setLiveMode] = useState(true) // Start in LIVE mode
  const [selectedTarget, setSelectedTarget] = useState('WIN$N')
  const [targetsMeta, setTargetsMeta] = useState([]) // From /api/irai/targets
  const [seriesInfo, setSeriesInfo] = useState({}) // display_name, icon from series response
  const [series, setSeries] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  
  // The effective date: LIVE = today (from backend), or manually selected
  const effectiveDate = liveMode ? (dates.length > 0 ? dates[0] : selectedDate) : selectedDate

  // Fetch dates + targets list once (and poll every 60s in live mode to detect new sessions)
  useEffect(() => {
    function loadDates() {
      if (FIREBASE_URL) {
        const url = FIREBASE_URL.endsWith('.json') ? FIREBASE_URL : `${FIREBASE_URL.replace(/\/$/, '')}/db.json`
        fetch(url)
          .then(r => r.json())
          .then(data => {
            const d = data?.dates?.dates || []
            setDates(d)
            if (d.length > 0 && !selectedDate) setSelectedDate(d[0])
          })
          .catch(e => setError(e.message))
      } else {
        fetch(`${API}/api/irai/dates`)
          .then(r => r.json())
          .then(data => {
            setDates(data.dates || [])
            if (data.dates?.length > 0 && !selectedDate) setSelectedDate(data.dates[0])
          })
          .catch(e => setError(e.message))
      }
    }
    loadDates()
    const poll = setInterval(loadDates, 60_000)
    return () => clearInterval(poll)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (FIREBASE_URL) {
      const url = FIREBASE_URL.endsWith('.json') ? FIREBASE_URL : `${FIREBASE_URL.replace(/\/$/, '')}/db.json`
      fetch(url)
        .then(r => r.json())
        .then(data => setTargetsMeta((data?.targets?.targets || []).filter(t => t.calibrated)))
        .catch(() => {})
    } else {
      fetch(`${API}/api/irai/targets`)
        .then(r => r.json())
        .then(data => setTargetsMeta((data.targets || []).filter(t => t.calibrated)))
        .catch(() => {})
    }
  }, [])

  // Fetch series data (silent = no loading spinner on auto-refresh)
  const fetchSeries = useCallback((date, target, silent = false) => {
    if (!date) return
    if (!silent) {
      setLoading(true)
      // Clear previous data so we don't show ghost data from a previously selected target
      setSeries([])
      setSummary(null)
      setSeriesInfo({})
      setError(null)
    }
    
    if (FIREBASE_URL) {
      const url = FIREBASE_URL.endsWith('.json') ? FIREBASE_URL : `${FIREBASE_URL.replace(/\/$/, '')}/db.json`
      fetch(url)
        .then(r => r.json())
        .then(data => {
          if (data.error) { setError(data.error); setLoading(false); return }
          const safeTarget = target.replace('$', '_').replace('.', '_')
          const s = data?.series?.[safeTarget] || []
          const sum = data?.summaries?.[safeTarget] || {}
          const tMeta = data?.targets?.targets?.find(t => t.target === target) || {}
          const processed = s.map(x => ({
            ...x,
            time: x.timestamp ? x.timestamp.substring(11, 16) : '00:00',
          }))
          setSeries(processed)
          setSummary(sum)
          setSeriesInfo({ display_name: tMeta.display_name, icon: tMeta.icon })
          setLoading(false)
          setLastUpdate(new Date(data?.last_update ? data.last_update * 1000 : Date.now()))
          setError(null)
        })
        .catch(e => { setError(e.message); setLoading(false) })
    } else {
      fetch(`${API}/api/irai/series?session_date=${date}&target=${encodeURIComponent(target)}`)
        .then(r => r.json())
        .then(data => {
          if (data.error) { setError(data.error); setLoading(false); return }
          const processed = (data.series || []).map(s => ({
            ...s,
            time: s.timestamp ? s.timestamp.substring(11, 16) : '00:00',
          }))
          setSeries(processed)
          setSummary(data.summary)
          setSeriesInfo({ display_name: data.display_name, icon: data.icon })
          setLoading(false)
          setLastUpdate(new Date())
          setError(null)
        })
        .catch(e => { setError(e.message); setLoading(false) })
    }
  }, [])

  // Initial load on date/target/liveMode change + polling
  useEffect(() => {
    fetchSeries(effectiveDate, selectedTarget, false)
    
    if (!liveMode) return

    let mounted = true
    let pollTimer = null
    
    // Poll every 60s for updates (both Firebase and local)
    pollTimer = setInterval(() => {
      if (mounted) fetchSeries(effectiveDate, selectedTarget, true)
    }, 60_000)
    
    return () => {
      mounted = false
      if (pollTimer) clearInterval(pollTimer)
    }
  }, [effectiveDate, selectedTarget, liveMode, fetchSeries])

  const now = series.length > 0 ? series[series.length - 1] : null
  const hasFlow = now && 'flow_confirms' in now

  const isOffline = error && (error.includes('Failed to fetch') || error.includes('NetworkError') || error.includes('Load failed'));

  if (error && !series.length && isOffline && page === 'overview' && !FIREBASE_URL) {
    return (
      <div style={{
        minHeight: '100vh', background: '#0F172A', color: '#E2E8F0',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'JetBrains Mono, monospace',
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📡</div>
          <div style={{ fontSize: 16, color: '#F87171', marginBottom: 8 }}>
            Backend offline
          </div>
          <div style={{ fontSize: 12, color: '#64748B' }}>
            Inicie o servidor: python -m uvicorn backend.api.main:app --port 8888
          </div>
        </div>
      </div>
    )
  }

  // Applica NWE na série
  const seriesWithNWE = useMemo(() => {
    const rawNwe = computeNWE(series);
    return rawNwe.map(entry => {
      let z_compra = 0, z_venda = 0, z_neutro = entry.price_diverge_z || 0;
      if (entry.price_diverges) {
        if (entry.p_up > 55) { z_compra = entry.price_diverge_z; z_neutro = 0; }
        else if (entry.p_up < 45) { z_venda = entry.price_diverge_z; z_neutro = 0; }
      }
      return { ...entry, z_compra, z_venda, z_neutro };
    });
  }, [series]);
  const nweNow = seriesWithNWE.length > 0 ? seriesWithNWE[seriesWithNWE.length - 1] : null;

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap');
        :root {
          --font-serif: 'Instrument Serif', Georgia, serif;
          --font-sans: 'Instrument Sans', -apple-system, sans-serif;
          --font-mono: 'JetBrains Mono', ui-monospace, monospace;
          --amber: #C9A227;
          --amber-dim: #8A6E1A;
          --bg: #09090B;
          --bg-card: #0E0E11;
          --bg-card2: #111116;
          --border: #1C1C22;
          --border-dim: #141418;
          --grid: #13131A;
        }
        * { box-sizing: border-box; }
        body { margin: 0; background: var(--bg); }
        select { background: #0E0E11; color: #A0A0B0; border: 1px solid #1C1C22;
                 padding: 6px 12px; font-family: var(--font-mono); font-size: 11px;
                 border-radius: 4px; cursor: pointer; }
        select:hover { border-color: #2C2C38; }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
        /* Mobile Layout */
        .app-container { min-height: 100vh; background: var(--bg); color: #C8C8D4; font-family: var(--font-sans); padding: 24px 32px; max-width: 1400px; margin: 0 auto; }
        .app-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
        .app-header-controls { display: flex; align-items: center; gap: 10px; }
        .gauge-container { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 24px 32px; display: flex; justify-content: space-between; align-items: center; }
        .gauge-left { flex: 1; }
        .gauge-right { text-align: right; min-width: 140px; }
        .chart-container { background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 16px 16px 8px; margin-top: 16px; }
        .factors-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; align-items: stretch; }
        
        @media (max-width: 768px) {
          .app-container { padding: 16px 12px !important; }
          .app-header { flex-direction: column; align-items: flex-start !important; gap: 16px; }
          .app-header-controls { flex-wrap: wrap; }
          .gauge-container { flex-direction: column; align-items: flex-start !important; padding: 16px !important; gap: 16px; }
          .gauge-right { text-align: left !important; min-width: 0 !important; width: 100%; display: flex; flex-direction: column; gap: 4px; }
          .chart-container { padding: 12px 8px 8px !important; }
          .factors-grid { grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 6px; }
        }
      `}</style>
      {page === 'overview' ? (
        <Overview onSelectTarget={(target) => {
          setSelectedTarget(target)
          setPage('detail')
        }} />
      ) : (
      <div className="app-container">
        {/* Header */}
        <header className="app-header">
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
            <button
              onClick={() => setPage('overview')}
              style={{
                background: 'none', border: '1px solid #334155',
                borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
                fontFamily: 'var(--font-mono)', fontSize: 10, color: '#94A3B8',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = '#64748B'}
              onMouseLeave={e => e.currentTarget.style.borderColor = '#334155'}
            >← PAINEL</button>
            <h1 style={{
              fontFamily: 'var(--font-serif)', fontSize: 32, fontWeight: 400,
              margin: 0, color: 'var(--amber)',
              letterSpacing: '0.04em',
            }}>
              IRAI
            </h1>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 10, color: '#3A3A4A',
              letterSpacing: '0.12em', textTransform: 'uppercase',
            }}>Intraday Risk Appetite Index</span>
          </div>
          <div className="app-header-controls">
            {now && (
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 12, color: '#64748B',
              }}>{now.time} · barra {series.length}</span>
            )}
            {/* WS connection dot */}
            {liveMode && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 5,
                fontFamily: 'var(--font-mono)', fontSize: 9, color: '#4ADE80',
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: '#4ADE80',
                  boxShadow: '0 0 6px #4ADE80',
                  animation: 'pulse 2s infinite',
                }} />
                LIVE (60s)
              </div>
            )}
            {/* Target selector */}
            <select
              value={selectedTarget}
              onChange={e => setSelectedTarget(e.target.value)}
            >
              {targetsMeta.map(t => (
                <option key={t.target} value={t.target}>
                  {t.icon} {t.display_name}
                </option>
              ))}
            </select>
            {/* LIVE button + date dropdown */}
            {!FIREBASE_URL ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
                <button
                  onClick={() => setLiveMode(true)}
                  style={{
                    fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                    letterSpacing: '0.1em', padding: '6px 11px',
                    borderRadius: '4px 0 0 4px',
                    border: `1px solid ${liveMode ? '#4ADE80' : '#334155'}`,
                    borderRight: 'none',
                    background: liveMode ? 'rgba(74,222,128,0.12)' : '#1E293B',
                    color: liveMode ? '#4ADE80' : '#475569',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    display: 'flex', alignItems: 'center', gap: 5,
                  }}
                >
                  {liveMode && (
                    <span style={{
                      display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                      background: '#4ADE80',
                      boxShadow: '0 0 5px #4ADE80',
                      animation: 'pulse 2s infinite',
                    }} />
                  )}
                  LIVE
                </button>
                <select
                  value={liveMode ? (dates[0] || '') : (selectedDate || '')}
                  onChange={e => {
                    setLiveMode(false)
                    setSelectedDate(e.target.value)
                  }}
                  style={{
                    borderRadius: '0 4px 4px 0',
                    borderLeft: `1px solid ${liveMode ? '#4ADE8033' : '#334155'}`,
                    opacity: liveMode ? 0.5 : 1,
                  }}
                >
                  {dates.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
            ) : (
              <div style={{
                fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                letterSpacing: '0.1em', padding: '6px 11px',
                borderRadius: 4,
                border: '1px solid #4ADE80',
                background: 'rgba(74,222,128,0.12)',
                color: '#4ADE80',
                display: 'flex', alignItems: 'center', gap: 5,
              }}>
                <span style={{
                  display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                  background: '#4ADE80', boxShadow: '0 0 5px #4ADE80',
                  animation: 'pulse 2s infinite',
                }} />
                LIVE
              </div>
            )}
          </div>
        </header>

        {loading && (
          <div style={{ textAlign: 'center', padding: 60, color: '#64748B', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
            carregando sessão...
          </div>
        )}

        {error && !seriesWithNWE.length && !loading && (
          <div style={{ textAlign: 'center', padding: 100, color: '#64748B', fontFamily: 'var(--font-mono)' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>⏳</div>
            <div style={{ fontSize: 16, color: '#D4A84C', marginBottom: 8 }}>
              {isOffline ? 'Backend offline' : error}
            </div>
            <div style={{ fontSize: 12, color: '#64748B', marginTop: 12 }}>
              Aguardando o início do pregão ou os primeiros dados da sessão...
            </div>
          </div>
        )}

        {now && !loading && (
          <>
            {/* ── SIGNAL GAUGE ── */}
            <SignalGauge
              pUp={now.p_up}
              verdict={now.verdict}
              score={now.score}
              winReturn={now.win_return}
              flowConfirms={now.flow_confirms}
              cumDeltaNorm={now.cum_delta_norm}
              targetLabel={seriesInfo.display_name || selectedTarget}
              hasFlow={hasFlow}
              accuracy={seriesInfo.accuracy ?? 80}
              recentPUp={series.slice(-8).map(b => b.p_up).filter(v => v != null)}
              priceDiverges={now.price_diverges}
              nweUp={(nweNow?.nwe_slope || 0) >= 0}
              isPreview={now.is_preview}
            />

            {/* ── STACKED CHARTS: same X axis ── */}
            <div className="chart-container">
              {/* TOP: WIN vs IRAI */}
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <div>
                  <div style={{
                    fontFamily: 'var(--font-serif)', fontSize: 18, color: '#D0D0DC',
                  }}>
                    {seriesInfo.display_name || selectedTarget} <span style={{ fontStyle: 'italic', color: '#3A3A4A' }}>vs</span> IRAI
                  </div>
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--amber-dim)', marginTop: 2,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                  }}>rastro macro · fatores externos</div>
                </div>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 12, height: 2, background: '#E2E8F0' }} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#64748B' }}>{seriesInfo.display_name || selectedTarget}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 12, height: 2, background: '#D4A84C', borderTop: '1px dashed #D4A84C' }} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#64748B' }}>P(↑)</span>
                  </div>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={seriesWithNWE} syncId="irai" margin={{ top: 10, right: 45, left: 5, bottom: 0 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="time" tick={false} stroke="#1E293B" />
                  <YAxis
                    yAxisId="win" orientation="left" width={45}
                    domain={([dataMin, dataMax]) => { const max = Math.max(Math.abs(dataMin), Math.abs(dataMax), 0.01); return [-max, max]; }}
                    allowDataOverflow={true}
                    tick={{ fill: '#475569', fontSize: 8, fontFamily: 'JetBrains Mono' }}
                    stroke="#1E293B" tickFormatter={v => `${Number(v).toFixed(1)}%`}
                  />
                  <YAxis
                    yAxisId="pup" orientation="right" width={35} domain={[0, 100]}
                    ticks={[0, 25, 50, 75, 100]}
                    tick={{ fill: '#475569', fontSize: 8, fontFamily: 'JetBrains Mono' }}
                    stroke="#1E293B" tickFormatter={v => `${v}%`}
                  />
                  {/* Limiares do modelo — cruzar estas linhas ativa/desativa divergência */}
                  <ReferenceLine yAxisId="pup" y={60}
                    stroke="#4ADE80" strokeWidth={1} strokeDasharray="3 4"
                    label={{ value: 'compra', position: 'insideRight', fontSize: 7, fontFamily: 'JetBrains Mono', fill: '#4ADE8099', dy: -6 }}
                  />
                  <ReferenceLine yAxisId="pup" y={40}
                    stroke="#F87171" strokeWidth={1} strokeDasharray="3 4"
                    label={{ value: 'venda', position: 'insideRight', fontSize: 7, fontFamily: 'JetBrains Mono', fill: '#F8717199', dy: 8 }}
                  />
                  <ReferenceLine yAxisId="pup" y={50} stroke="#1E293B" strokeDasharray="2 6" />
                  <ReferenceLine yAxisId="win" y={0} stroke="#334155" strokeDasharray="2 2" />
                  <Tooltip content={<CustomTooltip />} />
                  <Line yAxisId="win" type="monotone" dataKey="win_return" stroke="#E2E8F0" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  <Line yAxisId="pup" type="monotone" dataKey="p_up" stroke="#D4A84C" strokeWidth={2} dot={false} strokeDasharray="6 3" isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>

              {/* MOVIMENTO DO ÍNDICE — NWE (Nadaraya-Watson Envelope) */}
              <div style={{ marginTop: 2, borderTop: '1px solid var(--border-dim)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0 4px' }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber-dim)',
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                  }}>
                    movimento {seriesInfo.display_name || selectedTarget}
                  </div>
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
                    color: (nweNow?.nwe_slope || 0) >= 0 ? '#4ADE80' : '#F87171',
                  }}>
                    {(nweNow?.nwe_slope || 0) >= 0 ? '▲ NWE ALTA' : '▼ NWE BAIXA'}
                    <span style={{ fontSize: 9, color: '#475569', marginLeft: 6, fontWeight: 400 }}>
                      {`bw=${NWE_BW}`} · {nweNow?.nwe_center?.toFixed(3)}%
                    </span>
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={180}>
                  <ComposedChart data={seriesWithNWE} syncId="irai" margin={{ top: 4, right: 45, left: 5, bottom: 0 }}>
                    <CartesianGrid stroke="var(--grid)" vertical={false} />
                    <XAxis
                      dataKey="time"
                      tick={{ fill: '#475569', fontSize: 8, fontFamily: 'JetBrains Mono' }}
                      stroke="#1E293B" interval={11}
                    />
                    <YAxis
                      yAxisId="nwe" orientation="left" width={45}
                      domain={([dataMin, dataMax]) => { const max = Math.max(Math.abs(dataMin), Math.abs(dataMax), 0.01); return [-max, max]; }}
                      allowDataOverflow={true}
                      tick={{ fill: '#475569', fontSize: 8, fontFamily: 'JetBrains Mono' }}
                      stroke="#1E293B"
                      tickFormatter={v => `${Number(v).toFixed(2)}%`}
                    />
                    <YAxis yAxisId="spacer" orientation="right" width={35} tick={false} stroke="transparent" />
                    <Tooltip
                      formatter={(v, name) => {
                        if (v === null || v === undefined) return [null, null];
                        const labels = { nwe_upper: 'Banda ↑', nwe_lower: 'Banda ↓', nwe_up: 'NWE ↑', nwe_down: 'NWE ↓', win_return: 'Preço' };
                        return [`${Number(v).toFixed(3)}%`, labels[name] || name]
                      }}
                      contentStyle={{ background: '#0E0E11', border: '1px solid #1C1C22', borderRadius: 4, fontFamily: 'JetBrains Mono', fontSize: 11 }}
                      labelStyle={{ color: '#6A6A7A' }}
                    />
                    {/* Envelope bands (dashed) */}
                    <Line yAxisId="nwe" type="monotone" dataKey="nwe_upper" dot={false}
                      stroke="#F87171" strokeWidth={1} strokeDasharray="4 3" isAnimationActive={false}
                    />
                    <Line yAxisId="nwe" type="monotone" dataKey="nwe_lower" dot={false}
                      stroke="#4ADE80" strokeWidth={1} strokeDasharray="4 3" isAnimationActive={false}
                    />
                    {/* NWE center line — split into up (green) and down (red) segments */}
                    <Line yAxisId="nwe" type="monotone" dataKey="nwe_up" dot={false}
                      stroke="#4ADE80" strokeWidth={1.5} isAnimationActive={false}
                      connectNulls={false}
                    />
                    <Line yAxisId="nwe" type="monotone" dataKey="nwe_down" dot={false}
                      stroke="#F87171" strokeWidth={1.5} isAnimationActive={false}
                      connectNulls={false}
                    />
                    {/* Price line */}
                    <Line yAxisId="nwe" type="monotone" dataKey="win_return" dot={false}
                      stroke="#E2E8F0" strokeWidth={1.5} isAnimationActive={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              
              {/* BOTTOM: Divergence Z-Score */}
              <div style={{ marginTop: 2, borderTop: '1px solid var(--border-dim)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0 4px' }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber-dim)',
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                  }}>
                    divergência de preço · z-score
                  </div>
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
                    color: now.price_diverges ? (now.p_up > 55 ? '#4ADE80' : '#F87171') : '#64748B',
                  }}>
                    {now.price_diverges ? (now.p_up > 55 ? '🟢 OPORTUNIDADE COMPRA' : '🔴 OPORTUNIDADE VENDA') : '✓ Z-SCORE ALINHADO'}
                    <span style={{ fontSize: 9, color: '#475569', marginLeft: 6, fontWeight: 400 }}>
                      z={now.price_diverge_z >= 0 ? '+' : ''}{now.price_diverge_z?.toFixed(2)}
                    </span>
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={120}>
                  <ComposedChart data={seriesWithNWE} syncId="irai" margin={{ top: 4, right: 45, left: 5, bottom: 0 }}>
                    <CartesianGrid stroke="var(--grid)" vertical={false} />
                    <XAxis
                      dataKey="time"
                      tick={{ fill: '#475569', fontSize: 8, fontFamily: 'JetBrains Mono' }}
                      stroke="#1E293B" interval={11}
                    />
                    <YAxis
                      yAxisId="z" orientation="left" width={45}
                      domain={[-2.5, 2.5]}
                      tick={{ fill: '#475569', fontSize: 8, fontFamily: 'JetBrains Mono' }}
                      stroke="#1E293B"
                    />
                    <YAxis yAxisId="spacer" orientation="right" width={35} tick={false} stroke="transparent" />
                    <ReferenceLine yAxisId="z" y={0} stroke="#475569" strokeWidth={1} strokeDasharray="4 4" />
                    <ReferenceLine yAxisId="z" y={0.5} stroke="#F8717133" strokeWidth={1} strokeDasharray="2 2" />
                    <ReferenceLine yAxisId="z" y={-0.5} stroke="#F8717133" strokeWidth={1} strokeDasharray="2 2" />
                    <Tooltip
                      formatter={(v, name, props) => {
                         let div = "✓ Alinhado";
                         if (props.payload.price_diverges) {
                             div = props.payload.p_up > 55 ? "Compra" : "Venda";
                         }
                         return [`${Number(v).toFixed(2)} (${div})`, 'Z-Score']
                      }}
                      contentStyle={{ background: '#0E0E11', border: '1px solid #1C1C22', borderRadius: 4, fontFamily: 'JetBrains Mono', fontSize: 11 }}
                      labelStyle={{ color: '#6A6A7A' }}
                    />
                    <Bar yAxisId="z" dataKey="z_neutro" stackId="z" fill="#334155" isAnimationActive={false} />
                    <Bar yAxisId="z" dataKey="z_compra" stackId="z" fill="#4ADE80" isAnimationActive={false} />
                    <Bar yAxisId="z" dataKey="z_venda" stackId="z" fill="#F87171" isAnimationActive={false} />
                    <Brush 
                      dataKey="time" 
                      height={20} 
                      stroke="#475569"
                      fill="#0E0E11"
                      travellerWidth={8}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* ── COMPACT FACTOR ROW ── */}
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--amber-dim)', letterSpacing: '0.1em', textTransform: 'uppercase', marginTop: 16, marginBottom: 6 }}>fatores</div>
            <div className="factors-grid">
              {Object.entries(now.factors || {}).map(([key, data]) => {
                if (!data) return null
                const meta = getFactorMeta(key)
                const contrib = data.contribution || 0
                const isFavorBuy = contrib > 0.02
                const isFavorSell = contrib < -0.02
                const color = isFavorBuy ? '#4ADE80' : isFavorSell ? '#F87171' : '#475569'
                const label = isFavorBuy ? 'COMPRA' : isFavorSell ? 'VENDA' : '—'
                const ret = data.ret || 0
                const intensity = Math.min(Math.abs(contrib) / 0.5, 1) * 100

                return (
                  <div key={key} style={{
                    background: isFavorBuy ? 'rgba(74,222,128,0.04)' : isFavorSell ? 'rgba(248,113,113,0.04)' : '#0E0E11',
                    border: `1px solid ${isFavorBuy ? 'rgba(74,222,128,0.14)' : isFavorSell ? 'rgba(248,113,113,0.14)' : '#1C1C22'}`,
                    borderRadius: 4, padding: '8px 10px',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontSize: 16 }}>{meta.icon}</span>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600, color,
                      }}>{label}</span>
                    </div>
                    <div style={{
                      fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600, color: '#CBD5E1',
                    }}>{meta.label}</div>
                    <div style={{
                      marginTop: 4, height: 2, background: '#1E293B', borderRadius: 1,
                      position: 'relative', overflow: 'hidden',
                    }}>
                      <div style={{
                        position: 'absolute', top: 0, bottom: 0, left: 0,
                        width: `${intensity}%`, background: color,
                        borderRadius: 1, transition: 'width 0.5s ease',
                      }} />
                    </div>
                    <div style={{
                      fontFamily: 'var(--font-mono)', fontSize: 8, color: '#475569', marginTop: 3,
                    }}>{ret >= 0 ? '+' : ''}{ret.toFixed(2)}%</div>
                  </div>
                )
              })}
              <div style={{
                background: now.score > 0 ? 'rgba(74,222,128,0.05)' : now.score < 0 ? 'rgba(248,113,113,0.05)' : '#0E0E11',
                border: `1px solid ${now.score > 0 ? 'rgba(74,222,128,0.15)' : now.score < 0 ? 'rgba(248,113,113,0.15)' : '#1C1C22'}`,
                borderRadius: 4, padding: '8px 14px', textAlign: 'center',
              }}>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 8, color: '#64748B',
                  letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4,
                }}>score</div>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 600,
                  color: now.score > 0 ? '#4ADE80' : now.score < 0 ? '#F87171' : '#94A3B8',
                }}>{now.score >= 0 ? '+' : ''}{now.score.toFixed(2)}</div>
              </div>
            </div>

            {/* ── FOOTER ── */}
            <div style={{
              marginTop: 16, paddingTop: 12, borderTop: '1px solid #141418',
              fontFamily: 'var(--font-mono)', fontSize: 10, color: '#2A2A36',
              display: 'flex', justifyContent: 'space-between',
            }}>
              <span>IRAI · {Object.keys(now.factors || {}).length} fatores cross-asset</span>
              <span>
                sessão {effectiveDate} ·
                {seriesInfo.display_name || selectedTarget} {now.win_open?.toFixed(0)} → {now.win_current?.toFixed(0)}
              </span>
            </div>
          </>
        )}
      </div>
      )}
    </>
  )
}
