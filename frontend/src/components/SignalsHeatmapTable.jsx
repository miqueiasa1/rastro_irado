import React from 'react';

export function SignalsHeatmapTable({ series = [], target = '' }) {
  if (!series || series.length === 0) return null;

  // Pegar os últimos 30 pontos para exibir a matriz de heatmap recente
  const recentSeries = series.slice(-30);

  const signalRows = [
    { key: 'hm_color_d', label: 'D (Divergência Retorno)' },
    { key: 'hm_color_p', label: 'P (Pullback NWE)' },
    { key: 'hm_color_z', label: 'Z (Z-Score Preço)' },
    { key: 'hm_color_e', label: 'E (Exaustão NWE)' },
    { key: 'hm_color_pr', label: 'PR (Pair Spread)' },
  ];

  return (
    <div style={{
      background: '#0E0E11',
      border: '1px solid #1C1C22',
      borderRadius: 6,
      padding: '12px 16px',
      marginTop: 16,
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 9,
        color: '#D4A84C',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        marginBottom: 10,
      }}>
        Matriz de Sinais Recentes (Heatmap D-P-Z-E) · {target}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-mono)', fontSize: 9 }}>
          <thead>
            <tr>
              <th style={{ textTransform: 'uppercase', color: '#64748B', textAlign: 'left', paddingBottom: 6 }}>Sinal</th>
              {recentSeries.map((s, idx) => (
                <th key={idx} style={{ color: '#475569', textAlign: 'center', paddingBottom: 6, fontWeight: 400 }}>
                  {(s.time || '').slice(-5)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {signalRows.map(row => (
              <tr key={row.key}>
                <td style={{ color: '#94A3B8', padding: '4px 8px 4px 0', whiteSpace: 'nowrap' }}>{row.label}</td>
                {recentSeries.map((s, idx) => {
                  const bg = s[row.key] || '#1E293B';
                  return (
                    <td key={idx} style={{ padding: 2, textAlign: 'center' }}>
                      <div
                        style={{
                          height: 14,
                          borderRadius: 2,
                          background: bg,
                          border: bg !== '#1E293B' && bg !== 'transparent' ? '1px solid rgba(255,255,255,0.2)' : 'none',
                        }}
                        title={`${row.label} - ${s.time}: ${bg}`}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
