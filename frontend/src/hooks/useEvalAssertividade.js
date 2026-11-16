import { useEffect, useState } from "react";

// Fase 21A: assertividade fora da amostra (harness diário, 18:45) para o ReliabilityCard.
// Local: GET /api/eval/assertividade. Público: nó eval/<target> do RTDB (só existe depois do
// deploy aprovado das regras; até lá a leitura falha e o card simplesmente não aparece).
const isLocalhost = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
const FIREBASE_URL = (import.meta.env.DEV || isLocalhost) ? null : import.meta.env.VITE_FIREBASE_URL;
const API = FIREBASE_URL ? null : 'http://localhost:8888';

export const EVAL_TARGETS = ['WIN$N', 'WDO$N'];
const POLL_MS = 10 * 60 * 1000;

export function useEvalAssertividade(target, win = '20') {
  const [state, setState] = useState({ key: null, data: null });
  const enabled = EVAL_TARGETS.includes(target);
  const key = `${target}|${win}`;

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    const load = () => {
      let url;
      if (FIREBASE_URL) {
        const baseUrl = FIREBASE_URL.replace(/\.json$/, '').replace(/\/$/, '');
        const safe = target.replace('$', '_').replace('.', '_');
        url = `${baseUrl}/eval/${safe}.json`;
      } else {
        url = `${API}/api/eval/assertividade?target=${encodeURIComponent(target)}&window=${win}`;
      }
      fetch(url)
        .then(r => (r.ok ? r.json() : null))
        .catch(() => null)
        .then(d => {
          if (cancelled) return;
          setState({ key, data: d && d.available ? d : null });
        });
    };
    load();
    const t = setInterval(load, POLL_MS);
    return () => { cancelled = true; clearInterval(t); };
  }, [enabled, target, win, key]);

  return enabled && state.key === key ? state.data : null;
}
