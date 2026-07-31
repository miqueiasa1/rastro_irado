import React from 'react';
import { TargetSelector } from './TargetSelector';

export function DetailHeader({
  onBackToOverview,
  now,
  validSeriesLength,
  liveMode,
  setLiveMode,
  selectedTarget,
  setSelectedTarget,
  targetsMeta,
  timeframe,
  setTimeframe,
  chartType,
  setChartType,
  dates,
  selectedDate,
  setSelectedDate,
  firebaseUrl,
  isLiveMode = true,
  seriesMode = "live",
  setSeriesMode,
}) {
  return (
    <header className="app-header">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <button
          onClick={onBackToOverview}
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
          }}>{now.time} · barra {validSeriesLength}</span>
        )}

        {liveMode && isLiveMode && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5,
            fontFamily: 'var(--font-mono)', fontSize: 9, color: '#4ADE80',
            background: 'rgba(74,222,128,0.1)', padding: '2px 8px', borderRadius: 4,
            border: '1px solid rgba(74,222,128,0.3)',
          }} title="Série imutável gravada em tempo real sem repainting retroativo">
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: '#4ADE80',
              boxShadow: '0 0 6px #4ADE80',
              animation: 'pulse 2s infinite',
            }} />
            LIVE IMUTÁVEL (Sem Repaint)
          </div>
        )}

        <TargetSelector
          targetsMeta={targetsMeta}
          selectedTarget={selectedTarget}
          onSelectTarget={setSelectedTarget}
        />

        {!firebaseUrl && (
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

        {/* Chart Style Toggle (Line vs Candle) */}
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
          >📈</button>
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
          >🕯️</button>
        </div>

        {/* LIVE button + date dropdown */}
        {!firebaseUrl ? (
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
                setLiveMode(false);
                setSelectedDate(e.target.value);
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
  );
}
