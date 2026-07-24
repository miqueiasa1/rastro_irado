import React from 'react';

export function TargetSelector({ targetsMeta = [], selectedTarget, onSelectTarget }) {
  const uniqueTargets = [];
  const seen = new Set();
  for (const t of targetsMeta) {
    if (t && t.target && !seen.has(t.target)) {
      seen.add(t.target);
      uniqueTargets.push(t);
    }
  }

  return (
    <select
      value={selectedTarget}
      onChange={e => onSelectTarget(e.target.value)}
      style={{
        padding: '6px 12px',
        borderRadius: 4,
        border: '1px solid #1C1C22',
        background: '#0E0E11',
        color: '#A0A0B0',
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        cursor: 'pointer',
      }}
    >
      {uniqueTargets.map(t => (
        <option key={t.target} value={t.target}>
          {t.icon} {t.display_name}
        </option>
      ))}
    </select>
  );
}
