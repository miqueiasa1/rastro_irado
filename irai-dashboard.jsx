import React, { useState, useMemo, useEffect } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceArea, ReferenceLine, AreaChart, Area, ComposedChart
} from 'recharts';

// ---------- Utilidades ----------
const mulberry32 = (seed) => {
  let a = seed;
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};
const rnorm = (rng) => {
  let u = 0, v = 0;
  while (u === 0) u = rng();
  while (v === 0) v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
};
const sigmoid = (x) => 1 / (1 + Math.exp(-x));

// ---------- Parâmetros do modelo ----------
// Vol diária típica em unidades de "%" (aproximações razoáveis)
const DAILY_VOL = { ewz: 1.8, vix: 5.0, dxy: 0.4, us10y: 2.0, ibov: 1.2 };

// Pesos (idealmente via regressão rolling 60d). Sinais: EWZ(+), VIX(-), DXY(-), US10Y(contextual)
const WEIGHTS = { ewz: 0.45, vix: -0.30, dxy: -0.25, us10y: 0.10 };

// Sessão B3: 10:00 → 17:55 em barras de 5 min = 96 barras
const BARS_PER_DAY = 96;
const ALPHA = 1.2; // calibração da sigmoid

function barToTime(bar) {
  const totalMinutes = 10 * 60 + bar * 5;
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function generateDay(seed, scenario) {
  const rng = mulberry32(seed);
  const bias = {
    normal: { ewz: 0, vix: 0, dxy: 0, us10y: 0 },
    riskOn: { ewz: 0.35, vix: -0.40, dxy: -0.25, us10y: 0.10 },
    riskOff: { ewz: -0.45, vix: 0.55, dxy: 0.35, us10y: -0.15 },
    choppy: { ewz: 0.05, vix: 0.08, dxy: 0, us10y: 0 },
  }[scenario];

  const barVol = {
    ewz: DAILY_VOL.ewz / Math.sqrt(BARS_PER_DAY),
    vix: DAILY_VOL.vix / Math.sqrt(BARS_PER_DAY),
    dxy: DAILY_VOL.dxy / Math.sqrt(BARS_PER_DAY),
    us10y: DAILY_VOL.us10y / Math.sqrt(BARS_PER_DAY),
    ibov: DAILY_VOL.ibov / Math.sqrt(BARS_PER_DAY),
  };

  const paths = { ewz: [0], vix: [0], dxy: [0], us10y: [0], ibov: [0] };

  for (let i = 1; i < BARS_PER_DAY; i++) {
    paths.ewz.push(paths.ewz[i - 1] + rnorm(rng) * barVol.ewz + bias.ewz * barVol.ewz);
    paths.vix.push(paths.vix[i - 1] + rnorm(rng) * barVol.vix + bias.vix * barVol.vix);
    paths.dxy.push(paths.dxy[i - 1] + rnorm(rng) * barVol.dxy + bias.dxy * barVol.dxy);
    paths.us10y.push(paths.us10y[i - 1] + rnorm(rng) * barVol.us10y + bias.us10y * barVol.us10y);

    // IBOV "verdadeiro" = função dos fatores + ruído idiossincrático
    const factorImpact =
      (0.55 * (paths.ewz[i] / DAILY_VOL.ewz) +
        -0.35 * (paths.vix[i] / DAILY_VOL.vix) +
        -0.30 * (paths.dxy[i] / DAILY_VOL.dxy) +
        0.10 * (paths.us10y[i] / DAILY_VOL.us10y)) *
      DAILY_VOL.ibov;
    const noise = rnorm(rng) * barVol.ibov * 0.7;
    paths.ibov.push(factorImpact + noise);
  }
  return paths;
}

function computeIRAI(paths) {
  const series = [];
  const bars = paths.ewz.length;

  for (let i = 0; i < bars; i++) {
    const t = (i + 1) / bars;
    const expVol = (v) => v * Math.sqrt(t);
    const z = {
      ewz: i === 0 ? 0 : paths.ewz[i] / expVol(DAILY_VOL.ewz),
      vix: i === 0 ? 0 : paths.vix[i] / expVol(DAILY_VOL.vix),
      dxy: i === 0 ? 0 : paths.dxy[i] / expVol(DAILY_VOL.dxy),
      us10y: i === 0 ? 0 : paths.us10y[i] / expVol(DAILY_VOL.us10y),
    };
    const c = {
      ewz: WEIGHTS.ewz * z.ewz,
      vix: WEIGHTS.vix * z.vix,
      dxy: WEIGHTS.dxy * z.dxy,
      us10y: WEIGHTS.us10y * z.us10y,
    };
    const score = c.ewz + c.vix + c.dxy + c.us10y;
    const pUp = sigmoid(ALPHA * score) * 100;

    series.push({
      bar: i,
      time: barToTime(i),
      pUp,
      score,
      z_ewz: z.ewz, z_vix: z.vix, z_dxy: z.dxy, z_us10y: z.us10y,
      c_ewz: c.ewz, c_vix: c.vix, c_dxy: c.dxy, c_us10y: c.us10y,
      ibov: paths.ibov[i],
      ewz: paths.ewz[i],
      vix: paths.vix[i],
      dxy: paths.dxy[i],
      us10y: paths.us10y[i],
    });
  }
  return series;
}

// ---------- Componentes visuais ----------
const FACTOR_META = {
  ewz:   { label: 'EWZ',    color: '#D4A84C', sign: '+', desc: 'ETF Brasil (NYSE)' },
  vix:   { label: 'VIX',    color: '#C25C5C', sign: '−', desc: 'Vol S&P 500' },
  dxy:   { label: 'DXY',    color: '#7DA3C2', sign: '−', desc: 'Dólar index' },
  us10y: { label: 'US10Y',  color: '#8FA668', sign: '±', desc: 'Treasury 10 anos' },
};

function StatCard({ label, value, unit, sublabel, accent }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 4,
      padding: '20px 22px',
      position: 'relative',
    }}>
      <div style={{
        fontFamily: 'var(--font-sans)',
        fontSize: 10,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'var(--text-dim)',
      }}>{label}</div>
      <div style={{
        fontFamily: 'var(--font-serif)',
        fontSize: 44,
        lineHeight: 1,
        marginTop: 10,
        color: accent || 'var(--text-primary)',
        fontWeight: 400,
      }}>
        {value}<span style={{ fontSize: 20, color: 'var(--text-dim)', marginLeft: 4 }}>{unit}</span>
      </div>
      {sublabel && (
        <div style={{
          marginTop: 10,
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: 'var(--text-secondary)',
        }}>{sublabel}</div>
      )}
    </div>
  );
}

function FactorBar({ fkey, z, contribution }) {
  const meta = FACTOR_META[fkey];
  const magnitude = Math.min(Math.abs(z) / 2.5, 1); // escala visual até ±2.5σ
  const direction = z >= 0 ? 'right' : 'left';
  return (
    <div style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <div>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            color: 'var(--text-primary)',
            fontWeight: 500,
            marginRight: 8,
          }}>{meta.label}</span>
          <span style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 10,
            color: 'var(--text-dim)',
            letterSpacing: '0.05em',
          }}>{meta.sign} · {meta.desc}</span>
        </div>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 13,
          color: z >= 0 ? 'var(--up)' : 'var(--down)',
          fontWeight: 500,
        }}>{z >= 0 ? '+' : ''}{z.toFixed(2)}σ</span>
      </div>
      <div style={{
        height: 4,
        background: 'var(--border)',
        position: 'relative',
        display: 'flex',
        justifyContent: 'center',
      }}>
        <div style={{
          position: 'absolute',
          left: '50%',
          top: -1,
          bottom: -1,
          width: 1,
          background: 'var(--text-dim)',
        }} />
        <div style={{
          position: 'absolute',
          [direction === 'right' ? 'left' : 'right']: '50%',
          top: 0,
          bottom: 0,
          width: `${magnitude * 50}%`,
          background: meta.color,
        }} />
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        color: 'var(--text-dim)',
        marginTop: 4,
        textAlign: 'right',
      }}>contrib {contribution >= 0 ? '+' : ''}{contribution.toFixed(3)}</div>
    </div>
  );
}

export default function IRAIDashboard() {
  const [seed, setSeed] = useState(7);
  const [scenario, setScenario] = useState('normal');
  const [currentBar, setCurrentBar] = useState(BARS_PER_DAY - 1);

  const paths = useMemo(() => generateDay(seed, scenario), [seed, scenario]);
  const series = useMemo(() => computeIRAI(paths), [paths]);

  // Regenerar para ter "variação" entre cenários
  const now = series[currentBar];
  const visible = series.slice(0, currentBar + 1);

  // Verdict textual
  const verdict = useMemo(() => {
    if (!now) return '';
    if (now.pUp > 65) return 'RISK-ON';
    if (now.pUp < 35) return 'RISK-OFF';
    if (now.pUp > 55) return 'levemente comprador';
    if (now.pUp < 45) return 'levemente vendedor';
    return 'indeciso';
  }, [now]);

  const verdictColor =
    now.pUp > 60 ? 'var(--up)' :
    now.pUp < 40 ? 'var(--down)' :
    'var(--text-secondary)';

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap');

        :root {
          --bg: #0a0a0d;
          --surface: #121217;
          --surface-el: #16161c;
          --border: #23232b;
          --border-light: #2d2d36;
          --text-primary: #E8E6E1;
          --text-secondary: #908A7D;
          --text-dim: #5A5549;
          --accent: #D4A84C;
          --up: #6FB38A;
          --down: #C25C5C;
          --neutral: #7A7F8A;
          --font-serif: 'Instrument Serif', Georgia, serif;
          --font-sans: 'Instrument Sans', -apple-system, sans-serif;
          --font-mono: 'JetBrains Mono', ui-monospace, monospace;
        }
        * { box-sizing: border-box; }
        body { margin: 0; background: var(--bg); }
      `}</style>

      <div style={{
        minHeight: '100vh',
        background: 'var(--bg)',
        color: 'var(--text-primary)',
        fontFamily: 'var(--font-sans)',
        padding: '32px 40px',
      }}>
        {/* Cabeçalho */}
        <header style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          borderBottom: '1px solid var(--border)',
          paddingBottom: 24,
          marginBottom: 32,
        }}>
          <div>
            <div style={{
              fontSize: 10,
              letterSpacing: '0.25em',
              textTransform: 'uppercase',
              color: 'var(--accent)',
              marginBottom: 8,
            }}>Intraday Risk Appetite Index</div>
            <h1 style={{
              fontFamily: 'var(--font-serif)',
              fontSize: 52,
              fontWeight: 400,
              margin: 0,
              letterSpacing: '-0.02em',
              lineHeight: 1,
            }}>
              IRAI <span style={{ fontStyle: 'italic', color: 'var(--text-dim)' }}>/ IBOV</span>
            </h1>
            <div style={{
              marginTop: 12,
              fontSize: 12,
              color: 'var(--text-secondary)',
              fontFamily: 'var(--font-mono)',
            }}>
              B3 · 10:00 → 17:55 BRT · reset diário · barras 5 min
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.1em', textTransform: 'uppercase', marginRight: 8 }}>cenário</span>
            {[
              { k: 'normal', label: 'Normal' },
              { k: 'riskOn', label: 'Risk-on' },
              { k: 'riskOff', label: 'Risk-off' },
              { k: 'choppy', label: 'Choppy' },
            ].map((s) => (
              <button
                key={s.k}
                onClick={() => { setScenario(s.k); setSeed(seed + 1); }}
                style={{
                  background: scenario === s.k ? 'var(--accent)' : 'transparent',
                  color: scenario === s.k ? 'var(--bg)' : 'var(--text-secondary)',
                  border: `1px solid ${scenario === s.k ? 'var(--accent)' : 'var(--border)'}`,
                  padding: '6px 14px',
                  fontFamily: 'var(--font-sans)',
                  fontSize: 11,
                  letterSpacing: '0.05em',
                  cursor: 'pointer',
                  borderRadius: 2,
                  transition: 'all 0.15s',
                }}
              >{s.label}</button>
            ))}
            <button
              onClick={() => setSeed(seed + 1)}
              style={{
                background: 'transparent',
                color: 'var(--text-dim)',
                border: '1px solid var(--border)',
                padding: '6px 10px',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                cursor: 'pointer',
                marginLeft: 8,
                borderRadius: 2,
              }}
            >↻</button>
          </div>
        </header>

        {/* Linha 1: stats principais */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
          <StatCard
            label="P(↑ fechamento)"
            value={now.pUp.toFixed(1)}
            unit="%"
            sublabel={`score composto ${now.score >= 0 ? '+' : ''}${now.score.toFixed(3)}`}
            accent={verdictColor}
          />
          <StatCard
            label="Regime atual"
            value={verdict.split(' ')[0]}
            unit=""
            sublabel={verdict.includes(' ') ? verdict.split(' ').slice(1).join(' ') : 'leitura cross-asset'}
            accent={verdictColor}
          />
          <StatCard
            label="Horário sessão"
            value={now.time}
            unit=""
            sublabel={`barra ${currentBar + 1} / ${BARS_PER_DAY}`}
          />
          <StatCard
            label="IBOV simulado"
            value={(now.ibov >= 0 ? '+' : '') + now.ibov.toFixed(2)}
            unit="%"
            sublabel="vs abertura"
            accent={now.ibov >= 0 ? 'var(--up)' : 'var(--down)'}
          />
        </div>

        {/* Linha 2: chart principal + sidebar */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16, marginBottom: 24 }}>
          <div style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            padding: 20,
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

            <div style={{ height: 280 }}>
              <ComposedChart width={760} height={280} data={visible} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="pUpFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#D4A84C" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#D4A84C" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1f1f26" vertical={false} />
                <XAxis
                  dataKey="time"
                  tick={{ fill: '#5A5549', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                  stroke="#2d2d36"
                  interval={11}
                />
                <YAxis
                  domain={[0, 100]}
                  ticks={[0, 25, 50, 75, 100]}
                  tick={{ fill: '#5A5549', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                  stroke="#2d2d36"
                  tickFormatter={(v) => `${v}%`}
                />
                <ReferenceArea y1={40} y2={60} fill="#23232b" fillOpacity={0.4} />
                <ReferenceLine y={50} stroke="#3a3a44" strokeDasharray="3 3" />
                <Tooltip
                  contentStyle={{
                    background: '#16161c',
                    border: '1px solid #2d2d36',
                    borderRadius: 2,
                    fontFamily: 'JetBrains Mono',
                    fontSize: 11,
                  }}
                  labelStyle={{ color: '#908A7D' }}
                  formatter={(v, n) => [`${v.toFixed(1)}%`, 'P(↑)']}
                />
                <Area type="monotone" dataKey="pUp" stroke="none" fill="url(#pUpFill)" />
                <Line
                  type="monotone"
                  dataKey="pUp"
                  stroke="#D4A84C"
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </div>
          </div>

          {/* Sidebar: fatores */}
          <div style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            padding: 20,
          }}>
            <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>
              Z-scores intraday
            </div>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: 18, marginBottom: 16, color: 'var(--text-secondary)' }}>
              <span style={{ fontStyle: 'italic' }}>zᵢ(t)</span> normalizado por vol
            </div>

            <FactorBar fkey="ewz" z={now.z_ewz} contribution={now.c_ewz} />
            <FactorBar fkey="vix" z={now.z_vix} contribution={now.c_vix} />
            <FactorBar fkey="dxy" z={now.z_dxy} contribution={now.c_dxy} />
            <FactorBar fkey="us10y" z={now.z_us10y} contribution={now.c_us10y} />

            <div style={{
              marginTop: 20,
              paddingTop: 16,
              borderTop: '1px solid var(--border-light)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
            }}>
              <span style={{ fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-dim)' }}>Score composto</span>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 18,
                color: now.score >= 0 ? 'var(--up)' : 'var(--down)',
              }}>
                {now.score >= 0 ? '+' : ''}{now.score.toFixed(3)}
              </span>
            </div>
          </div>
        </div>

        {/* Linha 3: contribuições empilhadas + IBOV real */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
          <div style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            padding: 20,
          }}>
            <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-dim)' }}>
              Contribuições por fator
            </div>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: 18, marginBottom: 16, color: 'var(--text-secondary)' }}>
              quem está <span style={{ fontStyle: 'italic' }}>puxando</span> o score
            </div>
            <div style={{ height: 180 }}>
              <AreaChart width={430} height={180} data={visible} stackOffset="sign" margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#1f1f26" vertical={false} />
                <XAxis dataKey="time" tick={{ fill: '#5A5549', fontSize: 9, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" interval={15} />
                <YAxis tick={{ fill: '#5A5549', fontSize: 9, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" />
                <ReferenceLine y={0} stroke="#3a3a44" />
                <Tooltip
                  contentStyle={{ background: '#16161c', border: '1px solid #2d2d36', borderRadius: 2, fontFamily: 'JetBrains Mono', fontSize: 11 }}
                  labelStyle={{ color: '#908A7D' }}
                />
                <Area type="monotone" dataKey="c_ewz" stackId="1" stroke={FACTOR_META.ewz.color} fill={FACTOR_META.ewz.color} fillOpacity={0.7} isAnimationActive={false} />
                <Area type="monotone" dataKey="c_vix" stackId="1" stroke={FACTOR_META.vix.color} fill={FACTOR_META.vix.color} fillOpacity={0.7} isAnimationActive={false} />
                <Area type="monotone" dataKey="c_dxy" stackId="1" stroke={FACTOR_META.dxy.color} fill={FACTOR_META.dxy.color} fillOpacity={0.7} isAnimationActive={false} />
                <Area type="monotone" dataKey="c_us10y" stackId="1" stroke={FACTOR_META.us10y.color} fill={FACTOR_META.us10y.color} fillOpacity={0.7} isAnimationActive={false} />
              </AreaChart>
            </div>
            <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
              {Object.entries(FACTOR_META).map(([k, m]) => (
                <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                  <span style={{ width: 10, height: 10, background: m.color, display: 'inline-block' }} />
                  {m.label}
                </div>
              ))}
            </div>
          </div>

          <div style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            padding: 20,
          }}>
            <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-dim)' }}>
              Validação visual
            </div>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: 18, marginBottom: 16, color: 'var(--text-secondary)' }}>
              IBOV <span style={{ fontStyle: 'italic' }}>real</span> vs P<sub>up</sub>
            </div>
            <div style={{ height: 180 }}>
              <LineChart width={430} height={180} data={visible} margin={{ top: 5, right: 25, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#1f1f26" vertical={false} />
                <XAxis dataKey="time" tick={{ fill: '#5A5549', fontSize: 9, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" interval={15} />
                <YAxis yAxisId="left" tick={{ fill: '#5A5549', fontSize: 9, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" tickFormatter={(v) => `${v.toFixed(1)}%`} />
                <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tick={{ fill: '#5A5549', fontSize: 9, fontFamily: 'JetBrains Mono' }} stroke="#2d2d36" tickFormatter={(v) => `${v}%`} />
                <ReferenceLine yAxisId="left" y={0} stroke="#3a3a44" />
                <Tooltip
                  contentStyle={{ background: '#16161c', border: '1px solid #2d2d36', borderRadius: 2, fontFamily: 'JetBrains Mono', fontSize: 11 }}
                  labelStyle={{ color: '#908A7D' }}
                />
                <Line yAxisId="left" type="monotone" dataKey="ibov" stroke="#E8E6E1" strokeWidth={1.5} dot={false} name="IBOV %" isAnimationActive={false} />
                <Line yAxisId="right" type="monotone" dataKey="pUp" stroke="#D4A84C" strokeWidth={1} strokeDasharray="3 2" dot={false} name="P(↑) %" isAnimationActive={false} />
              </LineChart>
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
              linha contínua: IBOV simulado · tracejado: IRAI
            </div>
          </div>
        </div>

        {/* Time slider */}
        <div style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          padding: '16px 20px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-dim)' }}>
              Scrub · reproduzir sessão
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
              {barToTime(currentBar)}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={BARS_PER_DAY - 1}
            value={currentBar}
            onChange={(e) => setCurrentBar(Number(e.target.value))}
            style={{ width: '100%', accentColor: '#D4A84C' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)' }}>
            <span>10:00</span><span>12:00</span><span>14:00</span><span>16:00</span><span>17:55</span>
          </div>
        </div>

        {/* Footer / metodologia */}
        <div style={{
          marginTop: 32,
          paddingTop: 20,
          borderTop: '1px solid var(--border)',
          fontSize: 11,
          color: 'var(--text-dim)',
          fontFamily: 'var(--font-mono)',
          lineHeight: 1.6,
        }}>
          <span style={{ color: 'var(--text-secondary)' }}>método:</span> zᵢ(t) = rᵢ(t) / (σᵢ · √t) · S(t) = Σ wᵢ·zᵢ(t) · P<sub>up</sub>(t) = σ(α·S)
          <span style={{ marginLeft: 16, color: 'var(--text-secondary)' }}>pesos:</span> EWZ {WEIGHTS.ewz > 0 ? '+' : ''}{WEIGHTS.ewz} · VIX {WEIGHTS.vix} · DXY {WEIGHTS.dxy} · US10Y {WEIGHTS.us10y > 0 ? '+' : ''}{WEIGHTS.us10y}
          <span style={{ marginLeft: 16, color: 'var(--text-secondary)' }}>α:</span> {ALPHA}
        </div>
      </div>
    </>
  );
}
