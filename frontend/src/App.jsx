import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useSwipeable } from 'react-swipeable'
import Overview from './Overview'
import GEX_LEVELS from './gexLevels'
import TVProbabilityChart from './components/TVProbabilityChart'
import TVNweChart from './components/TVNweChart'
import TVKalmanWeightsChart from './components/TVKalmanWeightsChart'
import TVPairwiseZScoreChart from './components/TVPairwiseZScoreChart'
import TVPriceDivergeZScoreChart from './components/TVPriceDivergeZScoreChart'

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

const FACTOR_COLORS = [
  '#4ADE80', '#60A5FA', '#FBBF24', '#C084FC',
  '#F87171', '#2DD4BF', '#F472B6', '#A3E635',
  '#FCD34D', '#A78BFA', '#34D399', '#FB923C'
];


/* ── Big Gauge ────────────────────────────────────── */
function SignalGauge({ title, pUp = 50, verdict, score = 0, winReturn, flowConfirms, cumDeltaNorm, targetLabel, hasFlow = true, accuracy = 80, recentPUp = [], priceDiverges, nweUp, nweUpper, nweLower, isPreview, winCurrent }) {
  const isBuy = pUp >= 60
  const isSell = pUp <= 40

  const signalText = isBuy ? 'ALTA' : isSell ? 'BAIXA' : 'NEUTRO'
  const signalColor = isBuy ? '#4ADE80' : isSell ? '#F87171' : '#94A3B8'

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
    const late = vals.slice(half).reduce((a, b) => a + b, 0) / (vals.length - half)
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

  const isReturnDivergentBuy = isBuy && winReturn < 0;
  const isReturnDivergentSell = isSell && winReturn > 0;
  const isNweExhaustionDown = nweUpper !== undefined && nweUpper !== null && winCurrent !== undefined && winCurrent !== null && winCurrent > nweUpper;
  const isNweExhaustionUp = nweLower !== undefined && nweLower !== null && winCurrent !== undefined && winCurrent !== null && winCurrent < nweLower;
  const isNweDivergentBuy = isBuy && nweUp === false;
  const isNweDivergentSell = isSell && nweUp === true;

  const hasAlert = isReturnDivergentBuy || isReturnDivergentSell;

  const alertClass = hasAlert ? (isBuy ? 'card-alert-green' : 'card-alert-red') : '';

  return (
    <div className={`gauge-container ${alertClass}`} style={{
      flex: '1 1 350px',
      display: 'flex', gap: 20, padding: 24, borderRadius: 12,
      background: 'linear-gradient(180deg, #111116 0%, #09090B 100%)',
      border: `1px solid ${signalColor}33`,
      boxShadow: `0 4px 20px -10px ${signalColor}20`,
      alignItems: 'center',
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
        {title && <div style={{
          fontSize: 10, fontFamily: 'var(--font-serif)', color: '#C9A227', marginBottom: 6, fontStyle: 'italic'
        }}>{title}</div>}
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
        {/* D: DIVERGÊNCIA DE RETORNO */}
        <div style={{
          marginTop: 6, fontFamily: 'var(--font-mono)', fontSize: 9,
          padding: '2px 6px', borderRadius: 4, display: 'inline-block', clear: 'both', float: 'left',
          background: (isReturnDivergentBuy || isReturnDivergentSell) ? (isReturnDivergentBuy ? 'rgba(74,222,128,0.12)' : 'rgba(248,113,113,0.12)') : 'rgba(148,163,184,0.08)',
          color: (isReturnDivergentBuy || isReturnDivergentSell) ? (isReturnDivergentBuy ? '#4ADE80' : '#F87171') : '#64748B',
          border: `1px solid ${(isReturnDivergentBuy || isReturnDivergentSell) ? (isReturnDivergentBuy ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)') : 'rgba(148,163,184,0.1)'}`,
        }}>
          {(isReturnDivergentBuy || isReturnDivergentSell) ? (isReturnDivergentBuy ? '🟢 DIVERGÊNCIA %' : '🔴 DIVERGÊNCIA %') : '✓ DIVERGÊNCIA %'}
        </div>

        {/* P: PULLBACK / NWE DIVERGENCE */}
        <div className={(isNweDivergentBuy || isNweDivergentSell) ? 'badge-blink' : ''} style={{
          marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 9,
          padding: '2px 6px', borderRadius: 4, display: 'inline-block', clear: 'both', float: 'left',
          background: (isNweDivergentBuy || isNweDivergentSell) ? (isNweDivergentBuy ? 'rgba(74,222,128,0.12)' : 'rgba(248,113,113,0.12)') : 'rgba(148,163,184,0.08)',
          color: (isNweDivergentBuy || isNweDivergentSell) ? (isNweDivergentBuy ? '#4ADE80' : '#F87171') : '#64748B',
          border: `1px solid ${(isNweDivergentBuy || isNweDivergentSell) ? (isNweDivergentBuy ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)') : 'rgba(148,163,184,0.1)'}`,
        }}>
          {(isNweDivergentBuy || isNweDivergentSell) ? (isNweDivergentBuy ? '🟢 PULLBACK NWE' : '🔴 PULLBACK NWE') : '✓ PULLBACK NWE'}
        </div>

        {/* Z: Z-SCORE SIGNAL */}
        <div className={priceDiverges ? 'badge-blink' : ''} style={{
          marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 9,
          padding: '2px 6px', borderRadius: 4, display: 'inline-block', clear: 'both', float: 'left',
          background: priceDiverges ? (isBuy ? 'rgba(74,222,128,0.12)' : 'rgba(248,113,113,0.12)') : 'rgba(148,163,184,0.08)',
          color: priceDiverges ? (isBuy ? '#4ADE80' : '#F87171') : '#64748B',
          border: `1px solid ${priceDiverges ? (isBuy ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)') : 'rgba(148,163,184,0.1)'}`,
        }}>
          {priceDiverges ? (isBuy ? '🟢 Z-SCORE COMPRA' : '🔴 Z-SCORE VENDA') : '✓ Z-SCORE'}
        </div>

        {/* E: EXAUSTÃO NWE */}
        <div className={(isNweExhaustionUp || isNweExhaustionDown) ? 'badge-blink' : ''} style={{
          marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 9,
          padding: '2px 6px', borderRadius: 4, display: 'inline-block', clear: 'both', float: 'left',
          background: (isNweExhaustionUp || isNweExhaustionDown) ? (isNweExhaustionUp ? 'rgba(74,222,128,0.12)' : 'rgba(248,113,113,0.12)') : 'rgba(148,163,184,0.08)',
          color: (isNweExhaustionUp || isNweExhaustionDown) ? (isNweExhaustionUp ? '#4ADE80' : '#F87171') : '#64748B',
          border: `1px solid ${(isNweExhaustionUp || isNweExhaustionDown) ? (isNweExhaustionUp ? 'rgba(74,222,128,0.4)' : 'rgba(248,113,113,0.4)') : 'rgba(148,163,184,0.1)'}`,
        }}>
          {(isNweExhaustionUp || isNweExhaustionDown) ? (isNweExhaustionUp ? '🟢 EXAUSTÃO NWE' : '🔴 EXAUSTÃO NWE') : '✓ EXAUSTÃO NWE'}
        </div>
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

  const label = isFavorBuy ? 'COMPRA' : isFavorSell ? 'VENDA' : 'NEUTRO'
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
  const d = payload[0].payload;
  const pUp = d.p_up_v1 != null ? d.p_up_v1 : d.p_up;
  const pUpV2 = d.p_up_v2;
  const winRet = d.win_return;
  const isBuy = pUp >= 60
  const isSell = pUp <= 40

  return (
    <div style={{
      background: '#0F172A', border: '1px solid #1E293B', borderRadius: 4,
      padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 11,
    }}>
      <div style={{ color: '#94A3B8', marginBottom: 6 }}>{label}</div>
      <div style={{ color: isBuy ? '#4ADE80' : isSell ? '#F87171' : '#CBD5E1', fontWeight: 600 }}>
        V1: {pUp?.toFixed(1)}%
        <span style={{ marginLeft: 8, fontSize: 10, fontWeight: 400 }}>
          {isBuy ? '▲ COMPRA' : isSell ? '▼ VENDA' : '— NEUTRO'}
        </span>
      </div>
      {pUpV2 !== undefined && (
        <div style={{ color: pUpV2 >= 60 ? '#4ADE80' : pUpV2 <= 40 ? '#F87171' : '#CBD5E1', fontWeight: 600, marginTop: 2 }}>
          V2: {pUpV2?.toFixed(1)}%
          <span style={{ marginLeft: 8, fontSize: 10, fontWeight: 400 }}>
            {pUpV2 >= 60 ? '▲ COMPRA' : pUpV2 <= 40 ? '▼ VENDA' : '— NEUTRO'}
          </span>
        </div>
      )}
      {winRet != null && (
        <div style={{ color: winRet >= 0 ? '#4ADE80' : '#F87171', marginTop: 2 }}>
          Retorno: {winRet >= 0 ? '+' : ''}{winRet.toFixed(3)}%
        </div>
      )}
    </div>
  )
}


/* ── Custom Dot Renderers for Recharts ────────────── */
const renderZScoreSquare = (fillColor) => (props) => {
  const { cx, cy } = props;
  if (!cx || !cy) return null;
  return (
    <rect
      cx={cx}
      cy={cy}
      x={cx - 4.5}
      y={cy - 4.5}
      width={9}
      height={9}
      fill={fillColor}
      stroke="#09090b"
      strokeWidth={1}
      rx={1}
    />
  );
};


/* ── Main App ────────────────────────────────────── */
const REFRESH_INTERVAL = 30_000 // 30 seconds (fallback polling)

// Helper: compute local time from UTC time string + offset in hours
function toLocalTime(utcTimeStr, offsetH) {
  if (!utcTimeStr || !offsetH) return null;
  const [hStr, mStr] = utcTimeStr.split(':');
  let h = (parseInt(hStr, 10) + offsetH + 24) % 24;
  return `${h.toString().padStart(2, '0')}:${mStr}`;
}

const padSeriesToFullDay = (series, isB3 = false, timeframe = 'M5') => {
  if (!series || series.length === 0) return series;

  const lastTimeStr = series[series.length - 1].time; // ex: "18:05"
  if (!lastTimeStr) return series;

  const [hStr, mStr] = lastTimeStr.split(":");
  let currentH = parseInt(hStr, 10);
  let currentM = parseInt(mStr, 10);

  const padded = [...series];

  let stepMinutes = 5;
  if (timeframe === 'M1') stepMinutes = 1;
  else if (timeframe === 'M2') stepMinutes = 2;
  else if (timeframe === 'M5') stepMinutes = 5;
  else if (timeframe === 'M15') stepMinutes = 15;
  else if (timeframe === 'M30') stepMinutes = 30;
  else if (timeframe === 'H1') stepMinutes = 60;

  let targetEndH = isB3 ? 0 : 23;
  let targetEndM = isB3 ? 30 : 59;
  
  if (timeframe === 'H1') {
    targetEndM = 0;
    if (isB3) targetEndH = 0;
  } else if (timeframe === 'M30') {
    targetEndM = 30;
  } else if (timeframe === 'M15') {
    targetEndM = 45;
  }

  const maxPaddedLength = series.length + Math.ceil(24 * 60 / stepMinutes);

  while (true) {
    if (currentH === targetEndH && currentM >= targetEndM) break;
    if (padded.length > maxPaddedLength) break; 

    currentM += stepMinutes;
    if (currentM >= 60) {
      currentH = (currentH + Math.floor(currentM / 60)) % 24;
      currentM = currentM % 60;
    }

    const h = currentH.toString().padStart(2, '0');
    const m = currentM.toString().padStart(2, '0');
    const timeTickmill = `${h}:${m}`;

    padded.push({
      time: timeTickmill,
      time_local: isB3 ? toLocalTime(timeTickmill, -6) : null
    });
  }
  return padded;
};

function parseTimeToTimestamp(dateStr, timeStr) {
  if (!timeStr) return 0;
  let year = 2026, month = 6, day = 26;
  if (dateStr && dateStr.includes("-")) {
    const parts = dateStr.split("-").map(Number);
    if (parts.length === 3 && !parts.some(isNaN)) {
      [year, month, day] = parts;
    }
  }
  const [hour, minute] = timeStr.split(":").map(Number);
  if (isNaN(hour) || isNaN(minute)) return 0;
  return Math.floor(Date.UTC(year, month - 1, day, hour, minute) / 1000);
}

export default function App() {
  const [page, setPage] = useState('overview')
  const [dates, setDates] = useState([])
  const [selectedDate, setSelectedDate] = useState(null)
  const [liveMode, setLiveMode] = useState(true) // Start in LIVE mode
  const [selectedTarget, setSelectedTarget] = useState('WIN$N')
  const [timeframe, setTimeframe] = useState('M5')
  const [chartType, setChartType] = useState('line') // 'line' | 'candle'
  const [targetsMeta, setTargetsMeta] = useState([]) // From /api/irai/targets
  const [seriesInfo, setSeriesInfo] = useState({}) // display_name, icon from series response
  const [series, setSeries] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [rastroView, setRastroView] = useState('both') // 'v1', 'v2', 'both'
  const [panOffsetY, setPanOffsetY] = useState(0)
  const [isDraggingY, setIsDraggingY] = useState(false)
  const dragStartY = useRef(0)
  const lastPanOffsetY = useRef(0)
  const pairSignalsMemory = useRef({}) // key: `${target}_${date}_${time}`, value: 'buy' | 'sell'
  const zscoreSignalsMemory = useRef({}) // key: `${target}_${date}_${time}`, value: 'buy' | 'sell'
  const isFirstLoadRef = useRef(true)
  const [showGex, setShowGex] = useState(true)
  const [showMidWalls, setShowMidWalls] = useState(false)

  // Refs for TradingView lightweight-charts
  const probChartRef = useRef(null)
  const nweChartRef = useRef(null)
  const kalmanChartRef = useRef(null)
  const pairZChartRef = useRef(null)
  const priceDivergeZChartRef = useRef(null)

  // The effective date: LIVE = today (from backend), or manually selected
  const effectiveDate = liveMode ? (dates.length > 0 ? dates[0] : selectedDate) : selectedDate

  // Swipe Handlers
  const handleNextTarget = useCallback(() => {
    if (targetsMeta.length === 0) return;
    const currentIndex = targetsMeta.findIndex(t => t.target === selectedTarget);
    if (currentIndex < targetsMeta.length - 1) {
      setSelectedTarget(targetsMeta[currentIndex + 1].target);
    } else {
      setSelectedTarget(targetsMeta[0].target);
    }
  }, [targetsMeta, selectedTarget]);

  const handlePrevTarget = useCallback(() => {
    if (targetsMeta.length === 0) return;
    const currentIndex = targetsMeta.findIndex(t => t.target === selectedTarget);
    if (currentIndex > 0) {
      setSelectedTarget(targetsMeta[currentIndex - 1].target);
    } else {
      setSelectedTarget(targetsMeta[targetsMeta.length - 1].target);
    }
  }, [targetsMeta, selectedTarget]);

  const targetSwipeHandlers = useSwipeable({
    onSwipedLeft: handleNextTarget,
    onSwipedRight: handlePrevTarget,
    trackMouse: false
  });

  // Fetch dates + targets list once (and poll every 120s in live mode to detect new sessions)
  useEffect(() => {
    function loadDates() {
      if (FIREBASE_URL) {
        const baseUrl = FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '')
        fetch(`${baseUrl}/dates.json`)
          .then(r => r.json())
          .then(data => {
            const d = data?.dates || []
            setDates(d)
            if (d.length > 0) setSelectedDate(prev => prev || d[0])
          })
          .catch(e => setError(e.message))
      } else {
        fetch(`${API}/api/irai/dates`)
          .then(r => r.json())
          .then(data => {
            const d = data.dates || []
            setDates(d)
            if (d.length > 0) setSelectedDate(prev => prev || d[0])
          })
          .catch(e => setError(e.message))
      }
    }
    loadDates()
    const poll = setInterval(loadDates, FIREBASE_URL ? 120_000 : 60_000)
    return () => clearInterval(poll)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (FIREBASE_URL) {
      const baseUrl = FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '')
      fetch(`${baseUrl}/targets.json`)
        .then(r => r.json())
        .then(data => setTargetsMeta((data?.targets || []).filter(t => t.calibrated)))
        .catch(() => { })
    } else {
      fetch(`${API}/api/irai/targets`)
        .then(r => r.json())
        .then(data => setTargetsMeta((data.targets || []).filter(t => t.calibrated)))
        .catch(() => { })
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
      pairSignalsMemory.current = {}
      zscoreSignalsMemory.current = {}
    }

    if (FIREBASE_URL) {
      const baseUrl = FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '')
      const safeTarget = target.replace('$', '_').replace('.', '_')
      
      const fetches = [
        fetch(`${baseUrl}/series/${safeTarget}.json`).then(r => r.json()),
        fetch(`${baseUrl}/summaries/${safeTarget}.json`).then(r => r.json()),
        fetch(`${baseUrl}/history/${safeTarget}.json`).then(r => r.json())
      ]
      
      const shouldFetchLastUpdate = silent || isFirstLoadRef.current
      if (shouldFetchLastUpdate) {
        isFirstLoadRef.current = false
        fetches.push(fetch(`${baseUrl}/last_update.json`).then(r => r.json()).catch(() => null))
      }

      Promise.all(fetches)
        .then(([seriesData, summariesData, historyData, lastUpdateData]) => {
          const tMeta = targetsMeta.find(t => t.target === target) || {}
          const s = seriesData || []
          const sum = summariesData || {}
          const history_closes = historyData || []

          const isB3 = tMeta.session_start_h && tMeta.session_start_h !== 0;
          const processed = s.map(x => {
            const timeDb = x.timestamp ? x.timestamp.substring(11, 16) : '00:00';
            const timeTickmill = timeDb;
            const timeBrt = isB3 ? toLocalTime(timeDb, -6) : null;
            return {
              ...x,
              time: timeTickmill,
              time_local: timeBrt,
            };
          });

          let sliced = processed;
          if (isB3) {
            sliced = processed.filter(s => {
              if (!s.time) return true;
              return s.time >= "09:00";
            });
            if (sliced.length === 0) sliced = processed;
          }

          setSeries(padSeriesToFullDay(sliced, isB3, timeframe))
          setSummary(sum)
          setSeriesInfo({ 
            display_name: tMeta.display_name, 
            icon: tMeta.icon, 
            history_closes, 
            tz_offset: isB3 ? -3 : 0, 
            tz_label: 'BRT' 
          })
          setLoading(false)
          if (shouldFetchLastUpdate && lastUpdateData !== undefined && lastUpdateData !== null) {
            setLastUpdate(new Date(lastUpdateData * 1000))
          }
          setError(null)
        })
        .catch(e => { setError(e.message); setLoading(false) })
    } else {
      fetch(`${API}/api/irai/series?session_date=${date}&target=${encodeURIComponent(target)}&version=v2&timeframe=${timeframe}`)
        .then(r => r.json())
        .then(data => {
          if (data.error) { setError(data.error); setLoading(false); return }
          const isB3 = data.is_b3 || false;
          const processed = (data.series || []).map(s => {
            const timeDb = s.timestamp ? s.timestamp.substring(11, 16) : '00:00';
            const timeTickmill = timeDb;
            const timeBrt = isB3 ? toLocalTime(timeDb, -6) : null;
            return {
              ...s,
              time: timeTickmill,
              time_local: timeBrt,
            };
          })
          let sliced = processed;
          if (isB3) {
            sliced = processed.filter(s => {
              if (!s.time) return true;
              return s.time >= "09:00";
            });
            if (sliced.length === 0) sliced = processed; // fallback
          }

          setSeries(padSeriesToFullDay(sliced, isB3, timeframe))
          setSummary(data.summary)
          setSeriesInfo({ display_name: data.display_name, icon: data.icon, history_closes: data.history_closes || [], tz_offset: isB3 ? -3 : 0, tz_label: 'BRT', accuracy: data.summary?.accuracy })
          setLoading(false)
          setLastUpdate(new Date())
          setError(null)
        })
        .catch(e => { setError(e.message); setLoading(false) })
    }
  }, [targetsMeta, timeframe])

  // Initial load on date/target/liveMode change + polling
  useEffect(() => {
    fetchSeries(effectiveDate, selectedTarget, false)

    if (!liveMode) return

    let mounted = true
    let pollTimer = null

    // Poll for updates (Firebase: every 120s, local: every 60s)
    pollTimer = setInterval(() => {
      if (mounted) fetchSeries(effectiveDate, selectedTarget, true)
    }, FIREBASE_URL ? 120_000 : 60_000)
    
    return () => {
      mounted = false
      if (pollTimer) clearInterval(pollTimer)
    }
  }, [effectiveDate, selectedTarget, liveMode, fetchSeries])

  const validSeries = useMemo(() => series.filter(s => s.win_current !== undefined), [series]);
  const now = validSeries.length > 0 ? validSeries[validSeries.length - 1] : null
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
    const rawNwe = series || [];
    
    // Find the last valid non-ghost entry index to identify the live bar
    let latestActiveIndex = -1;
    for (let i = rawNwe.length - 1; i >= 0; i--) {
      if (rawNwe[i].win_current !== undefined && !rawNwe[i].is_ghost) {
        latestActiveIndex = i;
        break;
      }
    }

    return rawNwe.map((entry, index) => {
      let z_compra = 0, z_venda = 0, z_neutro = entry.price_diverge_z || 0;
      if (entry.price_diverges) {
        if (entry.p_up > 55) { z_compra = entry.price_diverge_z; z_neutro = 0; }
        else if (entry.p_up < 45) { z_venda = entry.price_diverge_z; z_neutro = 0; }
      }
      
      let pair_compra = undefined;
      let pair_venda = undefined;
      let hm_color_pr = '#1E293B';
      
      const pUpDir = entry.p_up != null ? entry.p_up : 50;
      const memKey = `${selectedTarget}_${effectiveDate}_${entry.time}`;
      const isLiveBar = (index === latestActiveIndex);

      // Determine if condition is met right now
      const isPairBuy = entry.pair_signal === 'buy' && pUpDir >= 50;
      const isPairSell = entry.pair_signal === 'sell' && pUpDir <= 50;

      // Only save to signals memory if it's the live active bar
      if (isLiveBar) {
        if (isPairBuy) pairSignalsMemory.current[memKey] = 'buy';
        else if (isPairSell) pairSignalsMemory.current[memKey] = 'sell';
      }

      // Historical bars evaluate condition strictly. Live bar uses memory to avoid repaint.
      const activeSignal = isLiveBar ? pairSignalsMemory.current[memKey] : (isPairBuy ? 'buy' : isPairSell ? 'sell' : null);
      if (activeSignal === 'buy') {
        pair_compra = entry.win_current;
        hm_color_pr = '#4ADE80';
      } else if (activeSignal === 'sell') {
        pair_venda = entry.win_current;
        hm_color_pr = '#F87171';
      }

      // Z-Score (Quadrado no gráfico)
      const isZBuy = entry.price_diverges && pUpDir > 55 && Math.abs(entry.price_diverge_z || 0) >= 2.0;
      const isZSell = entry.price_diverges && pUpDir < 45 && Math.abs(entry.price_diverge_z || 0) >= 2.0;

      // Only save to signals memory if it's the live active bar
      if (isLiveBar) {
        if (isZBuy) zscoreSignalsMemory.current[memKey] = 'buy';
        else if (isZSell) zscoreSignalsMemory.current[memKey] = 'sell';
      }

      // Historical bars evaluate condition strictly. Live bar uses memory to avoid repaint.
      const activeZSignal = isLiveBar ? zscoreSignalsMemory.current[memKey] : (isZBuy ? 'buy' : isZSell ? 'sell' : null);
      let z_compra_val = undefined;
      let z_venda_val = undefined;
      if (activeZSignal === 'buy') {
        z_compra_val = entry.win_current;
      } else if (activeZSignal === 'sell') {
        z_venda_val = entry.win_current;
      }

      const winReturn = entry.win_return || 0;
      const isNweExhaustionDown = entry.nwe_upper_price !== undefined && entry.nwe_upper_price !== null && entry.win_current !== undefined && entry.win_current !== null && entry.win_current > entry.nwe_upper_price;
      const isNweExhaustionUp = entry.nwe_lower_price !== undefined && entry.nwe_lower_price !== null && entry.win_current !== undefined && entry.win_current !== null && entry.win_current < entry.nwe_lower_price;

      // Heatmap Logic
      const pUp = entry.p_up != null ? entry.p_up : 50;
      const isBuy = pUp >= 60;
      const isSell = pUp <= 40;

      // D: Divergência de Retorno
      const isReturnDivergentBuy = isBuy && winReturn < 0;
      const isReturnDivergentSell = isSell && winReturn > 0;
      let hm_color_d = isReturnDivergentBuy ? '#4ADE80' : isReturnDivergentSell ? '#F87171' : '#1E293B';

      // P: Pullback NWE
      const nweUp = entry.nwe_slope !== undefined ? entry.nwe_slope >= 0 : undefined;
      const isNweDivergentBuy = isBuy && nweUp === false;
      const isNweDivergentSell = isSell && nweUp === true;
      let hm_color_p = isNweDivergentBuy ? '#4ADE80' : isNweDivergentSell ? '#F87171' : '#1E293B';

      // Z: Z-Score
      let hm_color_z = entry.price_diverges ? (entry.p_up > 55 ? '#4ADE80' : (entry.p_up < 45 ? '#F87171' : '#1E293B')) : '#1E293B';

      // E: Exaustão NWE
      let hm_color_e = isNweExhaustionUp ? '#4ADE80' : isNweExhaustionDown ? '#F87171' : '#1E293B';

      // Limpar sinais se o mercado estiver fechado (ghost bar)
      if (entry.is_ghost) {
        hm_color_d = 'transparent';
        hm_color_p = 'transparent';
        hm_color_z = 'transparent';
        hm_color_e = 'transparent';
        hm_color_pr = 'transparent';
        z_compra = 0;
        z_venda = 0;
        pair_compra = undefined;
        pair_venda = undefined;
        z_compra_val = undefined;
        z_venda_val = undefined;
      }

      const mappedEntry = {
        ...entry,
        z_compra, z_venda, z_neutro,
        pair_compra, pair_venda,
        z_compra_val, z_venda_val,
        hm_val: 1, hm_color_d, hm_color_p, hm_color_z, hm_color_pr, hm_color_e
      };

      // Flatten weights for Recharts
      const factors = entry.factors;
      if (factors) {
        Object.keys(factors).forEach(label => {
          mappedEntry[`weight_${label}`] = factors[label].weight;
        });
      }

      return mappedEntry;
    });
  }, [series, selectedTarget, effectiveDate]);
  const validSeriesWithNWE = useMemo(() => seriesWithNWE.filter(s => s.win_current !== undefined), [seriesWithNWE]);
  const nweNow = validSeriesWithNWE.length > 0 ? validSeriesWithNWE[validSeriesWithNWE.length - 1] : null;

  // Determine visibility of bottom charts
  const showKalman = now && now.factors && Object.keys(now.factors).length > 0;
  const showPairZ = seriesWithNWE.some(s => s.pair_z != null);
  const showPriceDivergeZ = seriesWithNWE.some(s => s.price_diverge_z != null);

  const lastActiveChart = useMemo(() => {
    if (showPriceDivergeZ) return 'priceDivergeZ';
    if (showPairZ) return 'pairZ';
    if (showKalman) return 'kalman';
    return 'nwe';
  }, [showPriceDivergeZ, showPairZ, showKalman]);

  // Build crosshair price maps as a ref (updated on data change, no re-subscription)
  const crosshairMapsRef = useRef({});
  useEffect(() => {
    const timeToProbPrice = new Map();
    const timeToNwePrice = new Map();
    const timeToKalmanPrice = new Map();
    const timeToPairZPrice = new Map();
    const timeToPriceDivergeZPrice = new Map();

    (seriesWithNWE || []).forEach(s => {
      const t = parseTimeToTimestamp(effectiveDate, s.time);
      if (t === 0) return;
      timeToProbPrice.set(t, s.p_up != null ? s.p_up : 50);
      timeToNwePrice.set(t, s.win_current ?? 0);
      if (s.factors) {
        const keys = Object.keys(s.factors);
        if (keys.length > 0) {
          timeToKalmanPrice.set(t, s[`weight_${keys[0]}`] ?? 0);
        }
      }
      timeToPairZPrice.set(t, s.pair_z ?? 0);
      timeToPriceDivergeZPrice.set(t, s.price_diverge_z ?? 0);
    });

    crosshairMapsRef.current = {
      timeToProbPrice, timeToNwePrice, timeToKalmanPrice,
      timeToPairZPrice, timeToPriceDivergeZPrice
    };
  }, [seriesWithNWE, effectiveDate]);

  // Compute a fingerprint of which charts are currently mounted
  const chartFingerprint = useMemo(() => {
    const parts = [];
    if (probChartRef.current?.getChart()) parts.push('prob');
    if (nweChartRef.current?.getChart()) parts.push('nwe');
    if (kalmanChartRef.current?.getChart()) parts.push('kalman');
    if (pairZChartRef.current?.getChart()) parts.push('pairZ');
    if (priceDivergeZChartRef.current?.getChart()) parts.push('priceDivergeZ');
    return parts.join(',');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seriesWithNWE, chartType]);

  // Synchronize timescale (zoom/pan) and crosshair (hover) for all TV charts
  // Re-bind when chart instances appear/disappear or chartType changes
  const savedRangeRef = useRef(null);
  useEffect(() => {
    let timeHandlers = [];
    let crosshairHandlers = [];

    const timer = setTimeout(() => {
      const charts = [
        { chart: probChartRef.current?.getChart(), series: probChartRef.current?.getMainSeries(), key: 'prob' },
        { chart: nweChartRef.current?.getChart(), series: nweChartRef.current?.getMainSeries(), key: 'nwe' },
        { chart: kalmanChartRef.current?.getChart(), series: kalmanChartRef.current?.getMainSeries(), key: 'kalman' },
        { chart: pairZChartRef.current?.getChart(), series: pairZChartRef.current?.getMainSeries(), key: 'pairZ' },
        { chart: priceDivergeZChartRef.current?.getChart(), series: priceDivergeZChartRef.current?.getMainSeries(), key: 'priceDivergeZ' }
      ].filter(c => c.chart);

      if (charts.length < 2) return;

      // Restore saved range to all charts (preserve user zoom across re-binds)
      if (savedRangeRef.current) {
        charts.forEach(c => {
          try {
            c.chart.timeScale().setVisibleLogicalRange(savedRangeRef.current);
          } catch (err) {}
        });
      }

      // Time scale synchronization with recursive protection based on range values
      charts.forEach(c => {
        const handler = (logicalRange) => {
          if (!logicalRange) return;
          savedRangeRef.current = logicalRange; // persist current range
          
          charts.forEach(other => {
            if (other.chart !== c.chart) {
              try {
                const otherRange = other.chart.timeScale().getVisibleLogicalRange();
                // If already extremely close to target range, skip updating to prevent loop
                if (otherRange &&
                    Math.abs(otherRange.from - logicalRange.from) < 0.05 &&
                    Math.abs(otherRange.to - logicalRange.to) < 0.05) {
                  return;
                }
                other.chart.timeScale().setVisibleLogicalRange(logicalRange);
              } catch (err) {}
            }
          });
        };
        c.chart.timeScale().subscribeVisibleLogicalRangeChange(handler);
        timeHandlers.push({ chart: c.chart, handler });
      });

      function getClosestTimestampForSeries(map, t) {
        if (!map || map.size === 0) return t;
        let closestKey = t;
        let minDiff = Infinity;
        for (let k of map.keys()) {
          let diff = Math.abs(k - t);
          if (diff < minDiff) {
            minDiff = diff;
            closestKey = k;
          }
        }
        return closestKey;
      }

      let isSyncingCrosshair = false;

      charts.forEach(c => {
        const handler = (param) => {
          if (isSyncingCrosshair) return;
          isSyncingCrosshair = true;

          const maps = crosshairMapsRef.current;

          if (!param.time) {
            charts.forEach(other => {
              if (other.chart !== c.chart) {
                try {
                  other.chart.clearCrosshairPosition();
                } catch (err) {}
              }
            });
          } else {
            const t = param.time;
            charts.forEach(other => {
              if (other.chart !== c.chart && other.series) {
                let price = 0;
                let targetTime = t;
                let priceMap = null;

                if (other.key === 'prob') priceMap = maps.timeToProbPrice;
                else if (other.key === 'nwe') priceMap = maps.timeToNwePrice;
                else if (other.key === 'kalman') priceMap = maps.timeToKalmanPrice;
                else if (other.key === 'pairZ') priceMap = maps.timeToPairZPrice;
                else if (other.key === 'priceDivergeZ') priceMap = maps.timeToPriceDivergeZPrice;

                if (priceMap) {
                  targetTime = getClosestTimestampForSeries(priceMap, t);
                  price = priceMap.get(targetTime) ?? 0;
                }

                try {
                  other.chart.setCrosshairPosition(price, targetTime, other.series);
                } catch (err) {}
              }
            });
          }
          isSyncingCrosshair = false;
        };
        c.chart.subscribeCrosshairMove(handler);
        crosshairHandlers.push({ chart: c.chart, handler });
      });
    }, 300);

    return () => {
      clearTimeout(timer);
      timeHandlers.forEach(h => {
        try {
          h.chart.timeScale().unsubscribeVisibleLogicalRangeChange(h.handler);
        } catch (err) {}
      });
      crosshairHandlers.forEach(h => {
        try {
          h.chart.unsubscribeCrosshairMove(h.handler);
        } catch (err) {}
      });
    };
  }, [chartType, chartFingerprint]);

  // Force timescale alignment on every data update to ensure they stay in sync
  const prevAlignKey = useRef('');
  useEffect(() => {
    if (!seriesWithNWE || seriesWithNWE.length === 0) return;

    const alignKey = `${timeframe}_${selectedTarget}_${effectiveDate}`;
    const isContextChange = prevAlignKey.current !== alignKey;
    if (isContextChange) {
      prevAlignKey.current = alignKey;
      savedRangeRef.current = null; // clear saved zoom on context change
    }

    const timer = setTimeout(() => {
      const charts = [
        probChartRef.current?.getChart(),
        nweChartRef.current?.getChart(),
        kalmanChartRef.current?.getChart(),
        pairZChartRef.current?.getChart(),
        priceDivergeZChartRef.current?.getChart()
      ].filter(Boolean);

      if (charts.length < 2) return;

      const validCount = seriesWithNWE.filter(s => s.win_current !== undefined).length;
      if (validCount > 0) {
        let range = savedRangeRef.current;
        if (!range) {
          range = {
            from: Math.max(0, validCount - 100),
            to: validCount + 15
          };
          savedRangeRef.current = range;
        }

        charts.forEach(chart => {
          try {
            chart.timeScale().setVisibleLogicalRange(range);
          } catch (err) {}
        });
      }
    }, 300); // 300ms to let all child setData calls settle

    return () => clearTimeout(timer);
  }, [seriesWithNWE, timeframe, selectedTarget, effectiveDate]);


  return (
    <>
      <style>{`
        @keyframes borderGlowGreen {
          0% { box-shadow: 0 0 5px rgba(74,222,128,0.2); border-color: rgba(74,222,128,0.3); }
          50% { box-shadow: 0 0 15px rgba(74,222,128,0.6), inset 0 0 10px rgba(74,222,128,0.1); border-color: rgba(74,222,128,0.8); }
          100% { box-shadow: 0 0 5px rgba(74,222,128,0.2); border-color: rgba(74,222,128,0.3); }
        }
        @keyframes borderGlowRed {
          0% { box-shadow: 0 0 5px rgba(248,113,113,0.2); border-color: rgba(248,113,113,0.3); }
          50% { box-shadow: 0 0 15px rgba(248,113,113,0.6), inset 0 0 10px rgba(248,113,113,0.1); border-color: rgba(248,113,113,0.8); }
          100% { box-shadow: 0 0 5px rgba(248,113,113,0.2); border-color: rgba(248,113,113,0.3); }
        }
        .card-alert-green { animation: borderGlowGreen 2s infinite ease-in-out; }
        .card-alert-red { animation: borderGlowRed 2s infinite ease-in-out; }

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
        <Overview
          onSelectTarget={(target) => {
            setSelectedTarget(target)
            setPage('detail')
          }}
        />
      ) : (
        <div className="app-container" {...targetSwipeHandlers}>
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
                }}>{now.time} · barra {validSeries.length}</span>
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

              {/* Timeframe Selector */}
              {!FIREBASE_URL && (
                <select
                  value={timeframe}
                  onChange={e => setTimeframe(e.target.value)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 4,
                    border: '1px solid #334155',
                    background: '#1E293B',
                    color: '#F8FAFC',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    cursor: 'pointer',
                  }}
                >
                  <option value="M1">1m</option>
                  <option value="M2">2m</option>
                  <option value="M5">5m</option>
                  <option value="M15">15m</option>
                  <option value="M30">30m</option>
                  <option value="H1">1h</option>
                </select>
              )}

              {/* Chart Style (Line vs Candles) */}
              <div style={{ display: 'flex', border: '1px solid #334155', borderRadius: 4, overflow: 'hidden' }}>
                <button
                  onClick={() => setChartType('line')}
                  style={{
                    padding: '6px 10px',
                    background: chartType === 'line' ? '#334155' : '#1E293B',
                    color: '#F8FAFC',
                    border: 'none',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    cursor: 'pointer',
                    transition: 'background 0.2s',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  title="Gráfico de Linha"
                >
                  📈
                </button>
                <button
                  onClick={() => setChartType('candle')}
                  style={{
                    padding: '6px 10px',
                    background: chartType === 'candle' ? '#334155' : '#1E293B',
                    color: '#F8FAFC',
                    border: 'none',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    cursor: 'pointer',
                    transition: 'background 0.2s',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  title="Gráfico de Velas"
                >
                  🕯️
                </button>
              </div>
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

          <main>
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
                  {liveMode
                    ? "Dica: O pregão pode estar fechado (fim de semana/feriado). Desative o LIVE 🟢 para visualizar dias anteriores."
                    : "Aguardando o início do pregão ou os primeiros dados da sessão..."}
                </div>
              </div>
            )}

            {now && !loading && (
              <>
                {/* ── SIGNAL GAUGES ── */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 16 }}>
                  {now.p_up != null && (
                    <SignalGauge
                      title="RASTRO MACRO"
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
                      nweUpper={nweNow?.nwe_upper_price}
                      nweLower={nweNow?.nwe_lower_price}
                      winCurrent={now.win_current}
                      isPreview={now.is_preview}
                    />
                  )}
                </div>

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
                      {now.pair_factor && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 8px', borderRadius: 4, background: '#0E0E11', border: '1px solid #1E293B' }}>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#64748B' }}>PAR ATIVO:</span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: '#C9A227', fontWeight: 600 }}>{now.pair_factor}</span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#64748B' }}>β:</span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: now.pair_beta > 0 ? '#4ADE80' : '#F87171' }}>{now.pair_beta > 0 ? '+' : ''}{now.pair_beta?.toFixed(3)}</span>
                          {now.pair_z != null && (
                            <>
                              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#64748B', marginLeft: 6 }}>Z:</span>
                              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: now.pair_z >= 0 ? '#4ADE80' : '#F87171' }}>{now.pair_z >= 0 ? '+' : ''}{now.pair_z.toFixed(2)}</span>
                            </>
                          )}
                        </div>
                      )}
                      {now.price_diverge_z != null && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 8px', borderRadius: 4, background: '#0E0E11', border: '1px solid #1E293B' }}>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#64748B' }}>DIV Z:</span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: now.price_diverge_z >= 0 ? '#4ADE80' : '#F87171' }}>{now.price_diverge_z >= 0 ? '+' : ''}{now.price_diverge_z.toFixed(2)}</span>
                        </div>
                      )}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <div style={{ width: 12, height: 2, background: '#E2E8F0' }} />
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#64748B' }}>{seriesInfo.display_name || selectedTarget}</span>
                      </div>
                      <div style={{ display: 'flex', border: '1px solid #1E293B', borderRadius: 4, overflow: 'hidden' }}>
                        <div
                          style={{
                            background: 'rgba(96,165,250,0.1)',
                            border: 'none', padding: '4px 8px',
                            display: 'flex', alignItems: 'center', gap: 4,
                          }}
                        >
                          <div style={{ width: 12, height: 2, background: '#60A5FA', borderTop: '1px dashed #60A5FA' }} />
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#60A5FA' }}>P(↑) Dinâmico</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <TVProbabilityChart
                    ref={probChartRef}
                    history={seriesWithNWE}
                    effectiveDate={effectiveDate}
                    selectedTarget={selectedTarget}
                    hideXAxis={lastActiveChart !== 'prob'}
                  />

                  {/* MOVIMENTO DO ÍNDICE — NWE (Nadaraya-Watson Envelope) */}
                  <div
                    style={{
                      marginTop: 2, borderTop: '1px solid var(--border-dim)',
                      cursor: isDraggingY ? 'grabbing' : 'grab'
                    }}
                    onMouseDown={(e) => {
                      setIsDraggingY(true);
                      dragStartY.current = e.clientY;
                      lastPanOffsetY.current = panOffsetY;
                    }}
                    onMouseMove={(e) => {
                      if (!isDraggingY) return;
                      const deltaY = e.clientY - dragStartY.current;
                      // Convert pixel movement to ratio of the chart height (320px).
                      // Moving mouse down (positive delta) shifts the chart down
                      // which means increasing the domain values.
                      setPanOffsetY(lastPanOffsetY.current + (deltaY / 320));
                    }}
                    onMouseUp={() => setIsDraggingY(false)}
                    onMouseLeave={() => setIsDraggingY(false)}
                    onDoubleClick={() => setPanOffsetY(0)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0 4px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{
                          fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber-dim)',
                          letterSpacing: '0.1em', textTransform: 'uppercase',
                        }}>
                          movimento {seriesInfo.display_name || selectedTarget}
                          {panOffsetY !== 0 && <span style={{ color: '#4ADE80', marginLeft: 8, fontSize: 8 }}>[Y-AXIS DESLOCADO - DUPLO CLIQUE PARA RESETAR]</span>}
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        {/* GEX toggle buttons */}
                        {/* GEX toggle buttons */}
                        {GEX_LEVELS[selectedTarget] && (
                          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                            <button
                              onClick={() => setShowGex(prev => !prev)}
                              style={{
                                fontFamily: 'var(--font-mono)', fontSize: 7, fontWeight: 700,
                                padding: '2px 6px', borderRadius: 3, cursor: 'pointer',
                                border: `1px solid ${showGex ? '#ffd600' : '#1E293B'}`,
                                background: showGex ? 'rgba(255,214,0,0.1)' : 'transparent',
                                color: showGex ? '#ffd600' : '#334155',
                                transition: 'all 0.15s', lineHeight: 1,
                              }}
                            >GEX</button>
                            {showGex && (
                              <button
                                onClick={() => setShowMidWalls(prev => !prev)}
                                style={{
                                  fontFamily: 'var(--font-mono)', fontSize: 7, fontWeight: 600,
                                  padding: '2px 5px', borderRadius: 3, cursor: 'pointer',
                                  border: `1px solid ${showMidWalls ? '#90a4ae' : '#1E293B'}`,
                                  background: showMidWalls ? 'rgba(144,164,174,0.1)' : 'transparent',
                                  color: showMidWalls ? '#90a4ae' : '#334155',
                                  transition: 'all 0.15s', lineHeight: 1,
                                }}
                              >MID</button>
                            )}
                          </div>
                        )}
                        <div style={{
                          fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
                          color: (nweNow?.nwe_slope || 0) >= 0 ? '#4ADE80' : '#F87171',
                        }}>
                          {(nweNow?.nwe_slope || 0) >= 0 ? '▲ NWE ALTA' : '▼ NWE BAIXA'}
                          <span style={{ fontSize: 9, color: '#475569', marginLeft: 6, fontWeight: 400 }}>
                            {`bw=8`} &middot; {
                              nweNow?.nwe_center_price >= 1000 
                                ? (nweNow.nwe_center_price / 1000).toFixed(1) + 'k' 
                                : nweNow?.nwe_center_price?.toFixed(2)
                            }
                          </span>
                        </div>
                      </div>
                    </div>
                    <TVNweChart
                      ref={nweChartRef}
                      history={seriesWithNWE}
                      walls={GEX_LEVELS[selectedTarget] || []}
                      showGex={showGex}
                      showMidWalls={showMidWalls}
                      effectiveDate={effectiveDate}
                      selectedTarget={selectedTarget}
                      hideXAxis={lastActiveChart !== 'nwe'}
                      chartType={chartType}
                    />
                  </div>

                  {/* BOTTOM: Signal Heatmap (D-P-Z-E) */}
                  <div style={{ marginTop: 2, borderTop: '1px solid var(--border-dim)', display: 'flex', flexDirection: 'column', gap: 16 }}>


                    {/* BOTTOM 1: Pairwise Z-Score (Pair Spread) */}
                    {seriesWithNWE.some(s => s.pair_z != null) && (
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0 4px' }}>
                          <div style={{
                            fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber-dim)',
                            letterSpacing: '0.1em', textTransform: 'uppercase',
                          }}>
                            z-score dinâmico (pair spread)
                          </div>
                        </div>
                        <TVPairwiseZScoreChart
                          ref={pairZChartRef}
                          history={seriesWithNWE}
                          effectiveDate={effectiveDate}
                          hideXAxis={lastActiveChart !== 'pairZ'}
                        />
                      </div>
                    )}

                    {/* BOTTOM 2: Price Divergence Z-Score */}
                    {seriesWithNWE.some(s => s.price_diverge_z != null) && (
                      <div style={{ marginTop: 16 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0 4px' }}>
                          <div style={{
                            fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber-dim)',
                            letterSpacing: '0.1em', textTransform: 'uppercase',
                          }}>
                            z-score dinâmico (divergência preço)
                          </div>
                        </div>
                        <TVPriceDivergeZScoreChart
                          ref={priceDivergeZChartRef}
                          history={seriesWithNWE}
                          effectiveDate={effectiveDate}
                          hideXAxis={lastActiveChart !== 'priceDivergeZ'}
                        />
                      </div>
                    )}

                    {/* BOTTOM 3: Dynamic Weights (Kalman Filter) */}
                    {now.factors && Object.keys(now.factors).length > 0 && (
                      <div style={{ marginTop: 16 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0 4px' }}>
                          <div style={{
                            fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber-dim)',
                            letterSpacing: '0.1em', textTransform: 'uppercase',
                          }}>
                            pesos dinâmicos (kalman filter)
                          </div>
                        </div>
                        <TVKalmanWeightsChart
                          ref={kalmanChartRef}
                          history={seriesWithNWE}
                          factorKeys={Object.keys(now.factors_v2 || now.factors || {})}
                          effectiveDate={effectiveDate}
                          hideXAxis={lastActiveChart !== 'kalman'}
                        />
                      </div>
                    )}
                  </div>
                </div>

                {/* ── COMPACT FACTOR ROW ── */}
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--amber-dim)', letterSpacing: '0.1em', textTransform: 'uppercase', marginTop: 16, marginBottom: 6 }}>fatores</div>
                <div className="factors-grid">
                  {Object.entries(now.factors_v2 || now.factors_v1 || now.factors || {}).map(([key, data]) => {
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
                          display: 'flex', justifyContent: 'space-between',
                        }}>
                          <span>{ret >= 0 ? '+' : ''}{ret.toFixed(2)}%</span>
                          {data.z_score !== undefined && (
                            <span>z: {data.z_score >= 0 ? '+' : ''}{data.z_score.toFixed(2)}</span>
                          )}
                        </div>
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
                      color: (now.score_v1 || now.score || 0) > 0 ? '#4ADE80' : (now.score_v1 || now.score || 0) < 0 ? '#F87171' : '#94A3B8',
                    }}>{(now.score_v1 || now.score || 0) >= 0 ? '+' : ''}{(now.score_v1 || now.score || 0).toFixed(2)}</div>
                  </div>
                </div>

                {/* ── FOOTER ── */}
                <div style={{
                  marginTop: 16, paddingTop: 12, borderTop: '1px solid #141418',
                  fontFamily: 'var(--font-mono)', fontSize: 10, color: '#2A2A36',
                  display: 'flex', justifyContent: 'space-between',
                }}>
                  <span>IRAI · {Object.keys(now.factors_v2 || now.factors_v1 || now.factors || {}).length} fatores cross-asset</span>
                  <span>
                    sessão {effectiveDate} ·
                    {seriesInfo.display_name || selectedTarget} {now.win_open?.toFixed(0)} → {now.win_current?.toFixed(0)}
                  </span>
                </div>
              </>
            )}
          </main>
        </div>
      )}
    </>
  )
}
