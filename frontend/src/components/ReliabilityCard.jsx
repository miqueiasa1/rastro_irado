import { useState } from "react";
import { isHonestUi } from "../utils/honesty";

// Fase 21A (REQ-U03): card de assertividade fora da amostra do P(↑) gravado ao vivo.
// Compara a leitura do dia (nowcast) com o horizonte de produto (60 min) nos últimos N pregões.
// Só leitura: os números vêm do harness diário; nada é recalculado no navegador.

const fmt = (x, nd = 2) => (x == null || Number.isNaN(x) ? '—' : Number(x).toFixed(nd).replace('.', ','));
const pct = (x) => (x == null ? '—' : `${(x * 100).toFixed(1).replace('.', ',')}`);

function MiniReliability({ bins, color }) {
  const W = 64, H = 64, pad = 4;
  const sx = (p) => pad + p * (W - 2 * pad);
  const sy = (p) => H - pad - p * (H - 2 * pad);
  const pts = (bins || []).filter(b => b && b.n > 0 && b.p_mean != null && b.freq_up != null);
  return (
    <svg width={W} height={H} style={{ background: '#0b1016', border: '1px solid #1E293B', borderRadius: 3 }}>
      <line x1={sx(0)} y1={sy(0)} x2={sx(1)} y2={sy(1)} stroke="#334155" strokeDasharray="2 2" strokeWidth={1} />
      {pts.length > 1 && (
        <polyline fill="none" stroke={color} strokeWidth={1.5}
          points={pts.map(b => `${sx(b.p_mean)},${sy(b.freq_up)}`).join(' ')} />
      )}
      {pts.map((b, i) => (
        <circle key={i} cx={sx(b.p_mean)} cy={sy(b.freq_up)} r={1.8} fill={color} />
      ))}
    </svg>
  );
}

function HorizonBlock({ title, h, color, badge }) {
  if (!h) return null;
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flex: 1, minWidth: 210 }}>
      <MiniReliability bins={h.reliability} color={color} />
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: '#94A3B8', lineHeight: 1.5 }}>
        <div style={{ color, fontWeight: 700, letterSpacing: '0.05em' }}>
          {title}
          {badge && (
            <span style={{ marginLeft: 6, padding: '0 4px', borderRadius: 3, border: `1px solid ${badge.color}`, color: badge.color, fontSize: 7 }}>
              {badge.label}
            </span>
          )}
        </div>
        <div>AUC {fmt(h.auc, 3)} <span style={{ color: '#475569' }}>({fmt(h.auc_lo, 2)}–{fmt(h.auc_hi, 2)})</span></div>
        <div>BSS {fmt(h.bss, 3)} · ECE {pct(h.ece)} pp</div>
        <div>acerto {pct(h.hit)}% · n {h.n ?? '—'}</div>
      </div>
    </div>
  );
}

export default function ReliabilityCard({ evalData, forecastUi = 'off' }) {
  const [open, setOpen] = useState(true);
  if (!evalData || !evalData.horizons) return null;
  const { horizons } = evalData;
  const honest = isHonestUi(forecastUi);
  const badge60 = horizons['60m']?.degraded
    ? (honest || forecastUi !== 'on'
        ? { label: 'SEM EDGE · SÓ LEITURA DO DIA', color: '#F59E0B' }
        : { label: 'DEGRADADO', color: '#F87171' })
    : null;
  const badgeNow = horizons.nowcast?.degraded ? { label: 'DEGRADADO', color: '#F87171' } : null;
  return (
    <div style={{ margin: '4px 0', padding: '6px 8px', border: '1px solid #1E293B', borderRadius: 4, background: 'rgba(15,23,42,0.6)' }}>
      <div
        onClick={() => setOpen(o => !o)}
        style={{ display: 'flex', justifyContent: 'space-between', cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--amber-dim)', letterSpacing: '0.1em', textTransform: 'uppercase' }}
      >
        <span>Assertividade fora da amostra · últimos {evalData.sessions ?? evalData.window_sessions} pregões ({evalData.first_session} a {evalData.last_session})</span>
        <span style={{ color: '#475569' }}>{open ? '▾' : '▸'}</span>
      </div>
      {open && (
        <>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 6 }}>
            <HorizonBlock title="LEITURA DO DIA (NOWCAST)" h={horizons.nowcast} color="#38BDF8" badge={badgeNow} />
            <HorizonBlock title="PREVISÃO 60 MIN" h={horizons['60m']} color="#F59E0B" badge={badge60} />
          </div>
          <div style={{ marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 7, color: '#475569' }}>
            Nowcast = sinal do dia até a barra; 60 min = sinal da próxima hora. BSS &lt; 0 = pior que a taxa-base.
            Curva: P médio × frequência de alta (diagonal = calibrado). Harness {evalData.harness_version} · {evalData.config_hash}.
          </div>
        </>
      )}
    </div>
  );
}
