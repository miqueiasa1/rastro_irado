import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useSwipeable } from 'react-swipeable'
import Overview from './Overview'
import GEX_LEVELS from './gexLevels'
import TVProbabilityChart from './components/TVProbabilityChart'
import TVNweChart from './components/TVNweChart'
import TVKalmanWeightsChart from './components/TVKalmanWeightsChart'
import TVPairwiseZScoreChart from './components/TVPairwiseZScoreChart'
import TVPriceDivergeZScoreChart from './components/TVPriceDivergeZScoreChart'
import TVGarchVolChart from './components/TVGarchVolChart'

// Importações Refatoradas
import { useIraiData } from './hooks/useIraiData'
import SignalGauge from './components/SignalGauge'
import { FACTOR_DISPLAY, getFactorMeta } from './utils/constants'
import { parseTimeToTimestamp } from './utils/time'
import { processSeriesSignals } from './utils/signalProcessor'
import { DetailHeader } from './components/DetailHeader'
import { isForexTarget } from './utils/forex'
import { isHonestUi } from './utils/honesty'

const FIREBASE_URL = import.meta.env.DEV ? null : import.meta.env.VITE_FIREBASE_URL




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


export default function App() {
  const [page, setPage] = useState('overview')
  const [liveMode, setLiveMode] = useState(true)
  const [selectedTarget, setSelectedTarget] = useState('WIN$N')
  const [timeframe, setTimeframe] = useState('M5')
  const [chartType, setChartType] = useState('line') // 'line' | 'candle'
  const [rastroView, setRastroView] = useState('both') // 'v1', 'v2', 'both'
  const [panOffsetY, setPanOffsetY] = useState(0)
  const [isDraggingY, setIsDraggingY] = useState(false)
  const dragStartY = useRef(0)
  const lastPanOffsetY = useRef(0)
  const pairSignalsMemory = useRef({}) // key: `${target}_${date}_${time}`, value: 'buy' | 'sell'
  const zscoreSignalsMemory = useRef({}) // key: `${target}_${date}_${time}`, value: 'buy' | 'sell'
  const [showGex, setShowGex] = useState(true)
  const [showMidWalls, setShowMidWalls] = useState(true)
  const [showGarchBands, setShowGarchBands] = useState(false)
  const [showPairContra, setShowPairContra] = useState(false)
  const [showPairPro, setShowPairPro] = useState(true)
  const [showDivContra, setShowDivContra] = useState(false)
  const [showDivPro, setShowDivPro] = useState(true)

  // Refs for TradingView lightweight-charts
  const probChartRef = useRef(null)
  const nweChartRef = useRef(null)
  const kalmanChartRef = useRef(null)
  const pairZChartRef = useRef(null)
  const pairFixedZChartRef = useRef(null)
  const priceDivergeZChartRef = useRef(null)

  // Consumindo dados via Custom Hook
  const {
    dates,
    selectedDate,
    setSelectedDate,
    effectiveDate,
    targetsMeta,
    series,
    summary,
    loading,
    error,
    lastUpdate,
    gexWalls,
    availableRuns,
    selectedRun,
    garchData,
    seriesInfo,
    fetchGexForRun,
  } = useIraiData({ selectedTarget, liveMode, timeframe });

  const garchVolPct = useMemo(() => {
    if (!garchData || !Array.isArray(garchData.forecast) || garchData.forecast.length === 0) return null;
    const h1 = garchData.forecast.find(f => f.step === 'h+1' || f.step === 'h.1') || garchData.forecast[0];
    return h1 ? h1.vol_forecast_pct : null;
  }, [garchData]);

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

  const [zRastroMode, setZRastroMode] = useState(() => {
    return localStorage.getItem('irai_z_rastro_mode') || 'basket'; // 'basket' or 'probit'
  });

  const handleToggleZRastroMode = useCallback((mode) => {
    setZRastroMode(mode);
    localStorage.setItem('irai_z_rastro_mode', mode);
  }, []);

  const validSeries = useMemo(() => series.filter(s => s.win_current !== undefined), [series]);
  const now = validSeries.length > 0 ? validSeries[validSeries.length - 1] : null
  const hasFlow = now && 'flow_confirms' in now
  const kalmanFactorKeysStr = Object.keys(now?.factors_v2 || now?.factors || {}).join('|')
  const kalmanFactorKeys = useMemo(
    () => (kalmanFactorKeysStr ? kalmanFactorKeysStr.split('|') : []),
    [kalmanFactorKeysStr]
  )

  const isOffline = error && (error.includes('Failed to fetch') || error.includes('NetworkError') || error.includes('Load failed'));



  // Applica NWE na série
  // Aplica NWE e Sinais Estatísticos na série
  const seriesWithNWE = useMemo(() => {
    const rawNwe = series || [];
    const processed = processSeriesSignals(rawNwe, seriesInfo, pairSignalsMemory, zscoreSignalsMemory);
    
    return processed.map(entry => {
      const mappedEntry = { ...entry, hm_val: 1 };
      const factors = entry.factors;
      if (factors) {
        Object.keys(factors).forEach(label => {
          mappedEntry[`weight_${label}`] = factors[label].weight;
        });
      }
      return mappedEntry;
    });
  }, [series, selectedTarget, effectiveDate, seriesInfo]);
  const validSeriesWithNWE = useMemo(() => seriesWithNWE.filter(s => s.win_current !== undefined), [seriesWithNWE]);
  const nweNow = validSeriesWithNWE.length > 0 ? validSeriesWithNWE[validSeriesWithNWE.length - 1] : null;

  // Determine visibility of bottom charts
  const showKalman = now && now.factors && Object.keys(now.factors).length > 0;
  // CRITICAL RULE: O gráfico de Pair Spread (WIN vs WDO) deve estar sempre visível para todos os ativos,
  // mesmo se pair_z estiver temporariamente nulo (ex: início do pregão/pré-mercado).
  const showPairZ = true;
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
    const timeToPairFixedZPrice = new Map();
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
      timeToPairFixedZPrice.set(t, s.pair_fixed_z ?? 0);
      timeToPriceDivergeZPrice.set(t, s.price_diverge_z ?? 0);
    });

    crosshairMapsRef.current = {
      timeToProbPrice, timeToNwePrice, timeToKalmanPrice,
      timeToPairZPrice, timeToPairFixedZPrice, timeToPriceDivergeZPrice
    };
  }, [seriesWithNWE, effectiveDate]);

  // Compute a fingerprint of which charts are currently mounted
  const chartFingerprint = useMemo(() => {
    const parts = [];
    if (probChartRef.current?.getChart()) parts.push('prob');
    if (nweChartRef.current?.getChart()) parts.push('nwe');
    if (kalmanChartRef.current?.getChart()) parts.push('kalman');
    if (pairZChartRef.current?.getChart()) parts.push('pairZ');
    if (pairFixedZChartRef.current?.getChart()) parts.push('pairFixedZ');
    if (priceDivergeZChartRef.current?.getChart()) parts.push('priceDivergeZ');
    return parts.join(',');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seriesWithNWE, chartType]);

  const savedRangeRef = useRef(null);
  const isSyncingRef = useRef(false);
  const prevValidCountRef = useRef(0);
  useEffect(() => {
    let timeHandlers = [];
    let crosshairHandlers = [];
    let boundFingerprint = '';

    const unbindAll = () => {
      timeHandlers.forEach(h => {
        try { h.chart.timeScale().unsubscribeVisibleLogicalRangeChange(h.handler); } catch { /* ignore */ }
      });
      crosshairHandlers.forEach(h => {
        try { h.chart.unsubscribeCrosshairMove(h.handler); } catch { /* ignore */ }
      });
      timeHandlers = [];
      crosshairHandlers = [];
    };

    // REGRA 2 (AGENTS.md): os gráficos montam DEPOIS deste efeito (a seção de detalhe só aparece
    // quando os dados chegam). Antes, o vínculo rodava uma única vez com os refs ainda nulos e a
    // sincronização ficava desligada até o próximo poll. Agora verificamos periodicamente quais
    // gráficos estão montados e (re)vinculamos sempre que o conjunto/instâncias mudar.
    const bindIfChanged = () => {
      const charts = [
        { chart: probChartRef.current?.getChart(), series: probChartRef.current?.getMainSeries(), key: 'prob' },
        { chart: nweChartRef.current?.getChart(), series: nweChartRef.current?.getMainSeries(), key: 'nwe' },
        { chart: kalmanChartRef.current?.getChart(), series: kalmanChartRef.current?.getMainSeries(), key: 'kalman' },
        { chart: pairZChartRef.current?.getChart(), series: pairZChartRef.current?.getMainSeries(), key: 'pairZ' },
        { chart: pairFixedZChartRef.current?.getChart(), series: pairFixedZChartRef.current?.getMainSeries(), key: 'pairFixedZ' },
        { chart: priceDivergeZChartRef.current?.getChart(), series: priceDivergeZChartRef.current?.getMainSeries(), key: 'priceDivergeZ' }
      ].filter(c => c.chart);

      if (charts.length < 2) return;

      // Impressão digital das instâncias montadas (detecta remontagem de qualquer gráfico)
      const fp = charts.map(c => c.key + ':' + (c.chart.__iraiId || (c.chart.__iraiId = Math.random().toString(36).slice(2)))).join(',');
      if (fp === boundFingerprint) return;
      boundFingerprint = fp;
      unbindAll();

      // Restore saved range to all charts (preserve user zoom across re-binds)
      if (savedRangeRef.current) {
        charts.forEach(c => {
          try {
            c.chart.timeScale().setVisibleLogicalRange(savedRangeRef.current);
          } catch (err) {}
        });
      }

      // CRITICAL RULE: Sincronização estrita de escala horizontal de tempo entre todos os gráficos.
      // O flag isSyncingRef evita loops recursivos e oscilações indesejadas no zoom/pan dos múltiplos painéis.
      charts.forEach(c => {
        const handler = (logicalRange) => {
          if (!logicalRange) return;
          if (isSyncingRef.current) return;
          
          isSyncingRef.current = true;
          savedRangeRef.current = logicalRange; // persist current range
          
          charts.forEach(other => {
            if (other.chart !== c.chart) {
              try {
                other.chart.timeScale().setVisibleLogicalRange(logicalRange);
              } catch (err) {}
            }
          });
          isSyncingRef.current = false;
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
                else if (other.key === 'pairFixedZ') priceMap = maps.timeToPairFixedZPrice;
                else if (other.key === 'priceDivergeZ') priceMap = maps.timeToPriceDivergeZPrice;

                if (priceMap) {
                  targetTime = getClosestTimestampForSeries(priceMap, t);
                  price = priceMap.get(targetTime) ?? 0;
                }

                try {
                  other.chart.setCrosshairPosition(price, targetTime, other.series);
                } catch { /* ignore */ }
              }
            });
          }
          isSyncingCrosshair = false;
        };
        c.chart.subscribeCrosshairMove(handler);
        crosshairHandlers.push({ chart: c.chart, handler });
      });
    };

    const timer = setTimeout(bindIfChanged, 50);
    const watcher = setInterval(bindIfChanged, 250);

    return () => {
      clearTimeout(timer);
      clearInterval(watcher);
      unbindAll();
    };
  }, [chartType, seriesWithNWE, timeframe, selectedTarget, effectiveDate, chartFingerprint]);

  // Force timescale alignment on every data update to ensure they stay in sync
  const prevAlignKey = useRef('');
  useEffect(() => {
    if (!seriesWithNWE || seriesWithNWE.length === 0) return;

    const alignKey = `${timeframe}_${selectedTarget}_${effectiveDate}`;
    const isContextChange = prevAlignKey.current !== alignKey;
    if (isContextChange) {
      prevAlignKey.current = alignKey;
      savedRangeRef.current = null; // clear saved zoom on context change
      prevValidCountRef.current = 0;
    }

    let attempts = 0;
    let timer = null;
    const align = () => {
      const charts = [
        probChartRef.current?.getChart(),
        nweChartRef.current?.getChart(),
        kalmanChartRef.current?.getChart(),
        pairZChartRef.current?.getChart(),
        pairFixedZChartRef.current?.getChart(),
        priceDivergeZChartRef.current?.getChart()
      ].filter(Boolean);

      // Gráficos ainda não montados: tenta de novo (até ~5s)
      if (charts.length < 2) {
        if (attempts++ < 20) timer = setTimeout(align, 250);
        return;
      }

      const validCount = seriesWithNWE.filter(s => s.win_current !== undefined).length;
      if (validCount > 0) {
        let range = savedRangeRef.current;
        
        // CRITICAL RULE: Preservação de zoom e posição (pan) contra resets automáticos nos ticks em tempo real.
        // Se o usuário não estava ativamente na borda direita (to >= prevValidCountRef.current - 2),
        // mantemos a janela visual intacta e não atualizamos sua visualização.
        if (range && prevValidCountRef.current > 0) {
          const isAtRightEdge = range.to >= prevValidCountRef.current - 2;
          if (isAtRightEdge) {
            const span = range.to - range.from;
            range = {
              from: Math.max(0, validCount - (span - 15)),
              to: validCount + 15
            };
            savedRangeRef.current = range;
          }
        } else if (!range) {
          range = {
            from: Math.max(0, validCount - 100),
            to: validCount + 15
          };
          savedRangeRef.current = range;
        }

        prevValidCountRef.current = validCount;

        isSyncingRef.current = true;
        charts.forEach(chart => {
          try {
            chart.timeScale().setVisibleLogicalRange(range);
          } catch {
            // ignore
          }
        });
        isSyncingRef.current = false;
      }
    };
    timer = setTimeout(align, 300); // 300ms to let all child setData calls settle

    return () => clearTimeout(timer);
  }, [seriesWithNWE, timeframe, selectedTarget, effectiveDate]);


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
    );
  }

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
          <DetailHeader
            onBackToOverview={() => setPage('overview')}
            now={now}
            validSeriesLength={validSeries.length}
            liveMode={liveMode}
            setLiveMode={setLiveMode}
            selectedTarget={selectedTarget}
            setSelectedTarget={setSelectedTarget}
            targetsMeta={targetsMeta}
            timeframe={timeframe}
            setTimeframe={setTimeframe}
            chartType={chartType}
            setChartType={setChartType}
            dates={dates}
            selectedDate={selectedDate}
            setSelectedDate={setSelectedDate}
            firebaseUrl={FIREBASE_URL}
          />

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

            {/* REGRA 1 (AGENTS.md): sem barras válidas (ex.: pré-mercado sem série), o painel principal
                não renderiza, mas o Pair Spread continua visível com eixos vazios. */}
            {!now && !loading && (
              <div style={{ marginTop: 16 }}>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber-dim)',
                  letterSpacing: '0.1em', textTransform: 'uppercase', padding: '2px 0 1px',
                }}>
                  z-score spread
                </div>
                <TVPairwiseZScoreChart
                  history={seriesWithNWE}
                  effectiveDate={effectiveDate}
                  valueKey="pair_z"
                  hideXAxis={false}
                  height="75px"
                />
              </div>
            )}

            {now && !loading && (
              <>
                {/* ── SIGNAL GAUGES ── */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 16 }}>
                  {now.p_up != null && (
                    <SignalGauge
                      title={isHonestUi(seriesInfo.forecast_ui) ? "LEITURA DO DIA (NOWCAST)" : "RASTRO MACRO"}
                      type="pd"
                      forecastUi={seriesInfo.forecast_ui}
                      pUp={now.p_up}
                      verdict={now.verdict}
                      score={now.score}
                      winReturn={now.win_return}
                      flowConfirms={now.flow_confirms}
                      cumDeltaNorm={now.cum_delta_norm}
                      targetLabel={seriesInfo.display_name || selectedTarget}
                      hasFlow={hasFlow}
                      accuracy={seriesInfo.accuracy ?? 80}
                      recentPUp={series.filter(b => b.p_up != null && !b.is_ghost).slice(-8).map(b => b.p_up)}
                      priceDiverges={now.price_diverges}
                      nweUp={(nweNow?.nwe_slope || 0) >= 0}
                      nweUpper={nweNow?.nwe_upper_price}
                      nweLower={nweNow?.nwe_lower_price}
                      nweCenter={nweNow?.nwe_center_price}
                      nweSlope={nweNow?.nwe_slope}
                      winCurrent={now.win_current}
                      isPreview={now.is_preview}
                    />
                  )}
                  {isForexTarget(selectedTarget) ? (
                    <>
                      <SignalGauge
                        title="POSIÇÃO ENVELOPE NWE"
                        type="nwe_pos"
                        winCurrent={now.win_current}
                        nweUpper={nweNow?.nwe_upper_price}
                        nweLower={nweNow?.nwe_lower_price}
                        nweCenter={nweNow?.nwe_center_price}
                        nweSlope={nweNow?.nwe_slope}
                        nweUp={(nweNow?.nwe_slope || 0) >= 0}
                        targetLabel={seriesInfo.display_name || selectedTarget}
                      />
                      <SignalGauge
                        title="CONFLUÊNCIA OPERACIONAL"
                        type="unified"
                        pUp={now.p_up}
                        score={now.score}
                        winCurrent={now.win_current}
                        nweUpper={nweNow?.nwe_upper_price}
                        nweLower={nweNow?.nwe_lower_price}
                        nweCenter={nweNow?.nwe_center_price}
                        nweSlope={nweNow?.nwe_slope}
                        nweUp={(nweNow?.nwe_slope || 0) >= 0}
                        targetLabel={seriesInfo.display_name || selectedTarget}
                      />
                    </>
                  ) : (
                    <>
                      <SignalGauge
                        title="Z-SCORE SPREAD"
                        type="pair_z"
                        zValue={now.pair_z}
                        forecastUi={seriesInfo.forecast_ui}
                        targetLabel={now.pair_factor || "Sem Par Ativo"}
                        beta={now.pair_beta}
                      />
                      {(selectedTarget === 'WIN$N' || selectedTarget === 'WDO$N' || now.pair_fixed_z != null) && (
                        <SignalGauge
                          title={selectedTarget === 'WIN$N' ? "Z-SCORE WDO" : (selectedTarget === 'WDO$N' ? "Z-SCORE WIN" : "Z-SCORE PAR FIXO")}
                          type="pair_fixed_z"
                          zValue={now.pair_fixed_z}
                          forecastUi={seriesInfo.forecast_ui}
                          targetLabel={now.pair_fixed_factor || (selectedTarget === 'WIN$N' ? "WDO" : "WIN")}
                          beta={now.pair_fixed_beta}
                        />
                      )}
                      <SignalGauge
                        title="Z-SCORE MACRO"
                        type="rastro_z"
                        zValue={now.price_diverge_z}
                        forecastUi={seriesInfo.forecast_ui}
                        targetLabel="Divergência Macro"
                      />
                    </>
                  )}
                </div>

                {/* ── STACKED CHARTS: same X axis ── */}
                <div className="chart-container">
                  {/* TOP: WIN vs IRAI */}
                  <div className="chart-header">
                    <div className="chart-header-title">
                      <div style={{
                        fontFamily: 'var(--font-sans)', fontSize: 14, fontWeight: 700, color: '#D0D0DC',
                      }}>
                        {seriesInfo.display_name || selectedTarget} <span style={{ fontStyle: 'italic', fontWeight: 400, color: '#64748B' }}>vs</span> IRAI
                      </div>
                      <div style={{
                        fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--amber-dim)', marginTop: 2,
                        letterSpacing: '0.1em', textTransform: 'uppercase',
                      }}>rastro macro · fatores externos</div>
                    </div>
                    <div className="chart-header-controls">
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
                            background: 'rgba(56,189,248,0.1)',
                            border: 'none', padding: '4px 8px',
                            display: 'flex', alignItems: 'center', gap: 4,
                          }}
                        >
                          <div style={{ width: 12, height: 2, background: '#38BDF8' }} />
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#38BDF8', fontWeight: 600 }}>P(↑) Rastro Macro</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <TVProbabilityChart
                    ref={probChartRef}
                    history={seriesWithNWE}
                    effectiveDate={effectiveDate}
                    selectedTarget={selectedTarget}
                    hideXAxis={true}
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
                        {((gexWalls && gexWalls.length > 0) || GEX_LEVELS[selectedTarget]) && (
                          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                            <button
                              onClick={() => setShowGarchBands(prev => !prev)}
                              style={{
                                fontFamily: 'var(--font-mono)', fontSize: 7, fontWeight: 700,
                                padding: '2px 6px', borderRadius: 3, cursor: 'pointer',
                                border: `1px solid ${showGarchBands ? '#38ef7d' : '#1E293B'}`,
                                background: showGarchBands ? 'rgba(56,239,125,0.1)' : 'transparent',
                                color: showGarchBands ? '#38ef7d' : '#334155',
                                transition: 'all 0.15s', lineHeight: 1,
                              }}
                            >GARCH</button>
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
                            {showGex && availableRuns.length > 1 && (
                              <select
                                value={selectedRun || ''}
                                onChange={(e) => fetchGexForRun(e.target.value)}
                                style={{
                                  fontFamily: 'var(--font-mono)', fontSize: 7, fontWeight: 600,
                                  padding: '1px 3px', borderRadius: 3, cursor: 'pointer',
                                  border: '1px solid #1E293B',
                                  background: '#0E0E11',
                                  color: '#ffd600',
                                  outline: 'none',
                                }}
                              >
                                {availableRuns.map(r => (
                                  <option key={r} value={r}>{r}</option>
                                ))}
                              </select>
                            )}
                          </div>
                        )}
                        <div style={{
                          fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
                          color: (nweNow?.nwe_slope || 0) >= 0 ? '#4ADE80' : '#F87171',
                        }}>
                          {(nweNow?.nwe_slope || 0) >= 0 ? '▲ Gauss ALTA' : '▼ Gauss BAIXA'}
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
                      walls={gexWalls}
                      showGex={showGex}
                      showMidWalls={showMidWalls}
                      effectiveDate={effectiveDate}
                      selectedTarget={selectedTarget}
                      hideXAxis={false}
                      chartType={chartType}
                      showGarchBands={showGarchBands}
                      garchVolPct={garchVolPct}
                    />
                  </div>

                  {/* BOTTOM: Signal Heatmap (D-P-Z-E) */}
                  <div style={{ marginTop: 2, borderTop: '1px solid var(--border-dim)', display: 'flex', flexDirection: 'column', gap: 2 }}>


                    {/* BOTTOM 1: Pairwise Z-Score (Pair Spread Dinâmico) */}
                    {/* CRITICAL RULE: Renderizado obrigatoriamente para todos os ativos conforme AGENTS.md Regra 1. */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '2px 0 1px' }}>
                        <div style={{
                          fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber-dim)',
                          letterSpacing: '0.1em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 6,
                        }}>
                          <span>z-score spread {now.pair_factor ? `(${now.pair_factor})` : ''}</span>
                          {now.pair_factor && now.pair_factor.includes('CESTA') && (
                            <span style={{
                              fontSize: 8, padding: '1px 4px', borderRadius: 3,
                              background: 'rgba(56, 189, 248, 0.15)', color: '#38BDF8',
                              border: '1px solid rgba(56, 189, 248, 0.3)', letterSpacing: '0.05em'
                            }}>
                              Arbitragem Forex
                            </span>
                          )}
                        </div>
                      </div>
                      <TVPairwiseZScoreChart
                        ref={pairZChartRef}
                        history={seriesWithNWE}
                        effectiveDate={effectiveDate}
                        valueKey="pair_z"
                        hideXAxis={true}
                        height="75px"
                      />
                    </div>

                    {/* BOTTOM 2: Fixed Pairwise Z-Score (Z-SCORE WDO / Z-SCORE WIN) */}
                    {(selectedTarget === 'WIN$N' || selectedTarget === 'WDO$N' || seriesWithNWE.some(s => s.pair_fixed_z != null)) && (
                      <div style={{ marginTop: 2 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '2px 0 1px' }}>
                          <div style={{
                            fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber-dim)',
                            letterSpacing: '0.1em', textTransform: 'uppercase',
                          }}>
                            {selectedTarget === 'WIN$N' ? "z-score wdo" : (selectedTarget === 'WDO$N' ? "z-score win" : "z-score par fixo")}
                          </div>
                        </div>
                        <TVPairwiseZScoreChart
                          ref={pairFixedZChartRef}
                          history={seriesWithNWE}
                          effectiveDate={effectiveDate}
                          valueKey="pair_fixed_z"
                          hideXAxis={true}
                          height="75px"
                        />
                      </div>
                    )}

                    {/* BOTTOM 2: Price Divergence Z-Score Macro */}
                    {seriesWithNWE.some(s => (s.price_diverge_z != null || s.price_diverge_basket_z != null || s.price_diverge_probit_z != null)) && (
                      <div style={{ marginTop: 2 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '2px 0 1px' }}>
                          <div style={{
                            fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber-dim)',
                            letterSpacing: '0.1em', textTransform: 'uppercase',
                          }}>
                            z-score rastro (macro) — {zRastroMode === 'basket' ? 'Resíduo Cesta' : 'Probit P(↑)'}
                          </div>
                          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                            <button
                              onClick={() => handleToggleZRastroMode('basket')}
                              style={{
                                background: zRastroMode === 'basket' ? 'rgba(217, 119, 6, 0.25)' : 'rgba(30, 41, 59, 0.5)',
                                color: zRastroMode === 'basket' ? '#FBBF24' : '#64748B',
                                border: `1px solid ${zRastroMode === 'basket' ? '#F59E0B' : '#334155'}`,
                                borderRadius: 3, padding: '1px 6px', fontSize: 8, fontFamily: 'var(--font-mono)',
                                cursor: 'pointer', fontWeight: zRastroMode === 'basket' ? 700 : 500,
                              }}
                              title="Modo 1: Spread Linear Multifatorial (Pair Trading Basket Spread)"
                            >
                              CESTA
                            </button>
                            <button
                              onClick={() => handleToggleZRastroMode('probit')}
                              style={{
                                background: zRastroMode === 'probit' ? 'rgba(217, 119, 6, 0.25)' : 'rgba(30, 41, 59, 0.5)',
                                color: zRastroMode === 'probit' ? '#FBBF24' : '#64748B',
                                border: `1px solid ${zRastroMode === 'probit' ? '#F59E0B' : '#334155'}`,
                                borderRadius: 3, padding: '1px 6px', fontSize: 8, fontFamily: 'var(--font-mono)',
                                cursor: 'pointer', fontWeight: zRastroMode === 'probit' ? 700 : 500,
                              }}
                              title="Modo 2: Divergência Probit Padronizada (Z Preço vs Z P_up)"
                            >
                              PROBIT P(↑)
                            </button>
                          </div>
                        </div>
                        <TVPriceDivergeZScoreChart
                          ref={priceDivergeZChartRef}
                          history={seriesWithNWE}
                          effectiveDate={effectiveDate}
                          hideXAxis={true}
                          threshold={2.0}
                          height="75px"
                          valueKey={zRastroMode === 'probit' ? 'price_diverge_probit_z' : 'price_diverge_basket_z'}
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
                            pesos dinâmicos
                          </div>
                        </div>
                        <TVKalmanWeightsChart
                          ref={kalmanChartRef}
                          history={seriesWithNWE}
                          factorKeys={kalmanFactorKeys}
                          effectiveDate={effectiveDate}
                          hideXAxis={true}
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
                    // Fase 17: em modo honesto o fator só "puxa" o dia para cima/baixo (sem COMPRA/VENDA)
                    const label = isHonestUi(seriesInfo.forecast_ui)
                      ? (isFavorBuy ? 'PUXA ↑' : isFavorSell ? 'PUXA ↓' : '—')
                      : (isFavorBuy ? 'COMPRA' : isFavorSell ? 'VENDA' : '—')
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


                {/* ── GARCH VOLATILITY PANEL ── */}
                {garchData && garchData.history && garchData.history.length > 0 && (
                  <>
                    {(() => {
                      const openPrice = now.win_open || (seriesWithNWE.length > 0 ? (seriesWithNWE[0].win_open || seriesWithNWE[0].win_current) : null);
                      if (!garchVolPct || !openPrice) return null;

                      // Identify Asset Categories
                      const isWin = selectedTarget.includes('WIN');
                      const isWdo = selectedTarget.includes('WDO') || selectedTarget.includes('DOL');
                      const isUSIndexOrGoldOrBtc = ['US500', 'US30', 'USTEC', 'XAUUSD', 'BTCUSD'].some(t => selectedTarget.includes(t));
                      const isStandardForex = ['EURUSD', 'GBPUSD'].some(t => selectedTarget.includes(t));
                      const isJpyForex = ['USDJPY', 'GBPJPY', 'EURJPY'].some(t => selectedTarget.includes(t));

                      // Base daily volatility (absolute price difference)
                      let baseVol = openPrice * (garchVolPct / 100);
                      let multiplier;
                      let unit = 'pts';
                      let decimalPlaces = 0;

                      if (isWin) {
                        multiplier = 1;
                        unit = 'pts';
                        decimalPlaces = 0;
                      } else if (isWdo) {
                        multiplier = 1;
                        unit = 'pts';
                        decimalPlaces = 1;
                      } else if (isUSIndexOrGoldOrBtc) {
                        multiplier = 100;
                        unit = 'pts';
                        decimalPlaces = 0;
                      } else if (isStandardForex) {
                        multiplier = 10000;
                        unit = 'pips';
                        decimalPlaces = 1;
                      } else if (isJpyForex) {
                        multiplier = 100;
                        unit = 'pips';
                        decimalPlaces = 1;
                      } else {
                        // Fallback generic
                        multiplier = 1;
                        unit = 'pts';
                        decimalPlaces = openPrice > 1000 ? 0 : (openPrice > 10 ? 2 : 5);
                      }

                      const volDia = baseVol * multiplier;
                      const stop10 = volDia * 0.10;
                      const stop12 = volDia * 0.12;
                      const stopTotal = volDia * 0.50; // 50% of GARCH expected vol

                      const format = (val) => {
                        if (unit === 'USD') {
                          return `$${Math.round(val).toLocaleString('pt-BR')}`;
                        }
                        if (decimalPlaces === 0) {
                          return `${Math.round(val).toLocaleString('pt-BR')} ${unit}`;
                        }
                        return `${val.toFixed(decimalPlaces)} ${unit}`;
                      };

                      const displayVol = `${format(volDia)} (${garchVolPct.toFixed(2)}%)`;
                      const displayStops = `${format(stop10)} | ${format(stop12)}`;
                      const displayTotal = `${format(stopTotal)} (${(garchVolPct * 0.5).toFixed(2)}%)`;

                      let financialNote = '';
                      if (isWin) {
                        financialNote = `💰 R$ ${(baseVol * 0.10 * 0.20).toFixed(2)} a R$ ${(baseVol * 0.12 * 0.20).toFixed(2)} por contrato de stop. Limite diário: R$ ${(baseVol * 0.50 * 0.20).toFixed(2)}.`;
                      } else if (isWdo) {
                        financialNote = `💰 R$ ${(baseVol * 0.10 * 10).toFixed(2)} a R$ ${(baseVol * 0.12 * 10).toFixed(2)} por contrato de stop. Limite diário: R$ ${(baseVol * 0.50 * 10).toFixed(2)}.`;
                      } else if (isUSIndexOrGoldOrBtc) {
                        financialNote = `📈 Multiplicador de pontos por 100 aplicado para exibição padrão do MetaTrader 5 (1 pt = 0.01 do preço).`;
                      } else if (isStandardForex || isJpyForex) {
                        financialNote = `📈 Exibição convertida para Pips (${isStandardForex ? '4ª casa decimal 0.0001' : '2ª casa decimal 0.01'}).`;
                      }

                      return (
                        <div style={{
                          background: '#0E0E11', border: '1px solid #1C1C22', borderRadius: 6,
                          padding: '12px 16px', marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10
                        }}>
                          <div style={{
                            fontFamily: 'var(--font-mono)', fontSize: 9, color: '#38ef7d',
                            letterSpacing: '0.1em', textTransform: 'uppercase', fontWeight: 700,
                            display: 'flex', alignItems: 'center', gap: 6
                          }}>
                            <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#38ef7d' }}></span>
                            Gestão de Risco Quantitativa ({selectedTarget.replace('$N', '')})
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 16 }}>
                            <div>
                              <div style={{ fontSize: 8, color: '#64748B', textTransform: 'uppercase', marginBottom: 2 }}>Vol Esperada (1σ)</div>
                              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: '#60A5FA' }}>
                                {displayVol}
                              </div>
                            </div>
                            <div>
                              <div style={{ fontSize: 8, color: '#64748B', textTransform: 'uppercase', marginBottom: 2 }}>Stop por Trade (10% | 12%)</div>
                              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: '#F87171' }}>
                                {displayStops}
                              </div>
                            </div>
                            <div>
                              <div style={{ fontSize: 8, color: '#64748B', textTransform: 'uppercase', marginBottom: 2 }}>Prejuízo Diário (50% GARCH)</div>
                              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: '#FFFFFF' }}>
                                {displayTotal} <span style={{ fontSize: 8, color: '#64748B', fontWeight: 400 }}>(4 a 5 ops)</span>
                              </div>
                            </div>
                          </div>
                          {financialNote && (
                            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: '#4ADE80', borderTop: '1px solid #1C1C22', paddingTop: 6 }}>
                              {financialNote}
                            </div>
                          )}
                        </div>
                      );
                    })()}
                    <TVGarchVolChart
                      history={garchData.history}
                      forecast={garchData.forecast}
                    />
                  </>
                )}

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
