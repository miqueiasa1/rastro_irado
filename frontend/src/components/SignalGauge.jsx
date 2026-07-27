import { calculateConviction, calculateStability } from "../utils/signalAnalyzer";

export default function SignalGauge({
  title,
  pUp = 50,
  score = 0,
  winReturn,
  flowConfirms,
  targetLabel,
  hasFlow = true,
  accuracy = 80,
  recentPUp = [],
  priceDiverges,
  nweUp,
  nweUpper,
  nweLower,
  isPreview,
  winCurrent,

  // New props for Z-Scores
  type = "pd",
  zValue = null,
  beta = null
}) {
  let isBuy = false;
  let isSell = false;
  let signalText = "NEUTRO";
  let signalColor = "#94A3B8";
  let angleRad = Math.PI * 0.5; // straight up
  let displayVal = "—";

  if (type === "pd") {
    isBuy = pUp >= 60;
    isSell = pUp <= 40;
    signalText = isBuy ? 'COMPRA' : isSell ? 'VENDA' : 'NEUTRO';
    signalColor = isBuy ? '#4ADE80' : isSell ? '#F87171' : '#94A3B8';
    angleRad = Math.PI * (1 - pUp / 100);
    displayVal = `${pUp.toFixed(1)}%`;
  } else {
    // Z-Score types: pair_z or rastro_z
    const z = zValue;
    displayVal = z != null ? (z >= 0 ? "+" : "") + z.toFixed(2) : "—";
    if (z != null) {
      if (z <= -2.0) {
        signalText = "COMPRA";
        signalColor = "#10B981"; // Emerald Green
        isBuy = true;
      } else if (z < -0.5) {
        signalText = "LEVEMENTE COMPRA";
        signalColor = "#4ADE80"; // Light Green
        isBuy = true;
      } else if (z >= 2.0) {
        signalText = "VENDA";
        signalColor = "#EF4444"; // Strong Red
        isSell = true;
      } else if (z > 0.5) {
        signalText = "LEVEMENTE VENDA";
        signalColor = "#F87171"; // Light Red
        isSell = true;
      } else {
        signalText = "NEUTRO";
        signalColor = "#94A3B8";
      }

      // Map Z-Score from [-3, 3] to [0, 100]
      let pUpMapped = 50 - (z * 50 / 3);
      pUpMapped = Math.max(0, Math.min(100, pUpMapped));
      angleRad = Math.PI * (1 - pUpMapped / 100);
    }
  }

  // ── Convicção calibrada por Shrinkage (only for PD type) ──
  const convictionData = type === "pd" 
    ? calculateConviction(pUp, accuracy, isPreview, signalColor, '#475569')
    : null;

  // ── Estabilidade (only for PD type) ──
  const stabilityData = type === "pd"
    ? calculateStability(recentPUp)
    : null;

  const isReturnDivergentBuy = type === "pd" && isBuy && winReturn < 0;
  const isReturnDivergentSell = type === "pd" && isSell && winReturn > 0;
  const isNweExhaustionDown = type === "pd" && nweUpper !== undefined && nweUpper !== null && winCurrent !== undefined && winCurrent !== null && winCurrent > nweUpper;
  const isNweExhaustionUp = type === "pd" && nweLower !== undefined && nweLower !== null && winCurrent !== undefined && winCurrent !== null && winCurrent < nweLower;
  const isNweDivergentBuy = type === "pd" && isBuy && nweUp === false;
  const isNweDivergentSell = type === "pd" && isSell && nweUp === true;

  const hasAlert = type === "pd" && (isReturnDivergentBuy || isReturnDivergentSell);
  const alertClass = hasAlert ? (isBuy ? 'card-alert-green' : 'card-alert-red') : '';

  return (
    <div className={`gauge-container ${alertClass}`} style={{
      flex: '1 1 300px',
      display: 'flex', flexDirection: 'column', gap: 8, padding: '10px 16px', borderRadius: 12,
      background: 'linear-gradient(180deg, #111116 0%, #09090B 100%)',
      border: `1px solid ${signalColor}33`,
      boxShadow: `0 4px 20px -10px ${signalColor}20`,
      alignItems: 'stretch',
    }}>
      {/* Top row: Gauge + Signal + Price */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', gap: 10, flexWrap: 'wrap' }}>
        {/* SVG Gauge */}
        <div style={{ position: 'relative', width: 90, height: 50, flexShrink: 0 }}>
          <svg viewBox="0 0 110 62" width="90" height="50">
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
            {type === 'pd' ? (
              <>
                <text x="6" y="56" fill="#F87171" fontSize="7" fontFamily="var(--font-mono)">↓</text>
                <text x="49" y="10" fill="#64748B" fontSize="7" fontFamily="var(--font-mono)">50%</text>
                <text x="96" y="56" fill="#4ADE80" fontSize="7" fontFamily="var(--font-mono)">↑</text>
              </>
            ) : (
              <>
                <text x="6" y="56" fill="#F87171" fontSize="7" fontFamily="var(--font-mono)">+3</text>
                <text x="52" y="10" fill="#64748B" fontSize="7" fontFamily="var(--font-mono)">0</text>
                <text x="96" y="56" fill="#4ADE80" fontSize="7" fontFamily="var(--font-mono)">-3</text>
              </>
            )}
            
            {/* Value in the middle */}
            <text
              x="55"
              y="48"
              textAnchor="middle"
              fill="#F8FAFC"
              fontSize="9"
              fontWeight="bold"
              fontFamily="var(--font-mono)"
            >
              {displayVal}
            </text>
          </svg>
        </div>

        {/* Signal text */}
        <div className="gauge-left" style={{ flex: 1, minWidth: 100 }}>
          {title && <div style={{
            fontSize: 9, fontFamily: 'var(--font-sans)', color: '#C9A227', marginBottom: 1, fontWeight: 600
          }}>{title}</div>}
          <div style={{
            fontFamily: 'var(--font-sans)', fontSize: 16, lineHeight: 1.1,
            color: signalColor, fontWeight: 700,
          }}>{signalText}</div>

          {/* Additional details row */}
          {type === "pd" && convictionData && stabilityData ? (
            <div style={{ marginTop: 2, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 9, color: '#64748B',
              }}>
                convicção{' '}
                <span style={{ color: convictionData.convColor, fontWeight: 600 }}>{convictionData.conviction}%</span>
                <span style={{ color: '#334155', fontSize: 8 }}> ({convictionData.convLabel})</span>
              </span>
              <span style={{ color: '#334155', fontSize: 9 }}>·</span>
              <span
                title={stabilityData.stabilityTip}
                style={{
                  fontFamily: 'var(--font-mono)', fontSize: 9, color: '#64748B', cursor: stabilityData.stabilityTip ? 'help' : 'default',
                  display: 'flex', alignItems: 'center', gap: 3
                }}>
                estabilidade{' '}
                <span style={{ color: stabilityData.stabilityColor, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 2 }}>
                  <span style={{ fontSize: 9 }}>{stabilityData.stabilityIcon}</span> {stabilityData.stability}
                </span>
              </span>
            </div>
          ) : (
            <div style={{ marginTop: 2, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 9, color: '#64748B',
              }}>
                Valor Z:{' '}
                <span style={{ color: signalColor, fontWeight: 600 }}>
                  {zValue != null ? (zValue >= 0 ? "+" : "") + zValue.toFixed(2) : "Sem dados"}
                </span>
              </span>
              {beta != null && (
                <>
                  <span style={{ color: '#334155', fontSize: 9 }}>·</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: '#64748B' }}>
                    β:{' '}
                    <span style={{ color: beta > 0 ? '#4ADE80' : '#F87171', fontWeight: 600 }}>
                      {beta > 0 ? '+' : ''}{beta.toFixed(3)}
                    </span>
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        {/* Local Signals / Actions */}
        <div className="gauge-right" style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              fontSize: 10, fontFamily: 'var(--font-mono)', color: signalColor,
              background: `${signalColor}15`, padding: '2px 6px', borderRadius: 4, fontWeight: 600
            }}>
              {type === "pd" ? `${pUp.toFixed(1)}%` : `Z = ${zValue != null ? zValue.toFixed(2) : 'N/A'}`}
            </span>
            {type === "pd" && score !== 0 && (
              <span style={{
                fontSize: 10, fontFamily: 'var(--font-mono)', color: score >= 0 ? '#4ADE80' : '#F87171',
                background: score >= 0 ? '#4ADE8015' : '#F8717115', padding: '2px 6px', borderRadius: 4, fontWeight: 600
              }}>
                {score >= 0 ? `+${score}` : score}
              </span>
            )}
          </div>

          <div style={{ fontSize: 11, fontWeight: 600, color: '#F1F5F9', fontFamily: 'var(--font-sans)', marginTop: 2 }}>
            {targetLabel}
          </div>

          {type === "pd" && hasFlow && flowConfirms !== undefined && (
            <div style={{
              fontSize: 8, fontFamily: 'var(--font-mono)', color: flowConfirms ? '#4ADE80' : '#94A3B8',
              letterSpacing: '0.05em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 3, marginTop: 1
            }}>
              <span style={{ fontSize: 10 }}>{flowConfirms ? '●' : '○'}</span>
              Fluxo {flowConfirms ? 'Confirmado' : 'Neutro'}
            </div>
          )}
        </div>
      </div>

      {/* Divergences / Alerts row (Only for PD) */}
      {type === "pd" && (isReturnDivergentBuy || isReturnDivergentSell || isNweDivergentBuy || isNweDivergentSell || isNweExhaustionUp || isNweExhaustionDown || priceDiverges) && (
        <div style={{
          borderTop: '1px dashed #1C1C22', padding: '6px 0 2px', display: 'flex', flexWrap: 'wrap', gap: '4px 10px',
          alignItems: 'center', marginTop: 4, paddingTop: 6
        }}>
          <span style={{ fontSize: 8, fontFamily: 'var(--font-mono)', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Alertas:</span>
          
          {priceDiverges && (
            <span style={{
              fontSize: 9, fontFamily: 'var(--font-mono)', color: '#FFD600',
              background: '#FFD60015', padding: '1px 5px', borderRadius: 3, fontWeight: 500,
              display: 'inline-flex', alignItems: 'center', gap: 2
            }}>
              ⚠️ DIVERGÊNCIA PREÇO
            </span>
          )}

          {isReturnDivergentBuy && (
            <span style={{
              fontSize: 9, fontFamily: 'var(--font-mono)', color: '#4ADE80',
              background: '#4ADE8015', padding: '1px 5px', borderRadius: 3, fontWeight: 500,
              display: 'inline-flex', alignItems: 'center', gap: 2
            }}>
              ⚡ COMPRA CONTRA RETORNO
            </span>
          )}
          {isReturnDivergentSell && (
            <span style={{
              fontSize: 9, fontFamily: 'var(--font-mono)', color: '#F87171',
              background: '#F8717115', padding: '1px 5px', borderRadius: 3, fontWeight: 500,
              display: 'inline-flex', alignItems: 'center', gap: 2
            }}>
              ⚡ VENDA CONTRA RETORNO
            </span>
          )}

          {isNweDivergentBuy && (
            <span style={{
              fontSize: 9, fontFamily: 'var(--font-mono)', color: '#FFD600',
              background: '#FFD60015', padding: '1px 5px', borderRadius: 3, fontWeight: 500,
              display: 'inline-flex', alignItems: 'center', gap: 2
            }}>
              📉 COMPRA VS GAUSS BAIXO
            </span>
          )}
          {isNweDivergentSell && (
            <span style={{
              fontSize: 9, fontFamily: 'var(--font-mono)', color: '#FFD600',
              background: '#FFD60015', padding: '1px 5px', borderRadius: 3, fontWeight: 500,
              display: 'inline-flex', alignItems: 'center', gap: 2
            }}>
              📈 VENDA VS GAUSS ALTO
            </span>
          )}

          {isNweExhaustionDown && (
            <span style={{
              fontSize: 9, fontFamily: 'var(--font-mono)', color: '#F87171',
              background: '#F8717115', padding: '1px 5px', borderRadius: 3, fontWeight: 600,
              display: 'inline-flex', alignItems: 'center', gap: 2
            }}>
              🚨 EXAUSTÃO GAUSS (TOPO)
            </span>
          )}
          {isNweExhaustionUp && (
            <span style={{
              fontSize: 9, fontFamily: 'var(--font-mono)', color: '#4ADE80',
              background: '#4ADE8015', padding: '1px 5px', borderRadius: 3, fontWeight: 600,
              display: 'inline-flex', alignItems: 'center', gap: 2
            }}>
              🚨 EXAUSTÃO GAUSS (FUNDO)
            </span>
          )}
        </div>
      )}
    </div>
  );
}
