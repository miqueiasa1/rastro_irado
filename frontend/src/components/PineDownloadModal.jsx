import React, { useState, useEffect, useRef } from 'react';

const isLocalhost = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
const DEFAULT_FIREBASE_URL = (import.meta.env.DEV || isLocalhost) ? null : import.meta.env.VITE_FIREBASE_URL;
const DEFAULT_API = DEFAULT_FIREBASE_URL ? null : 'http://localhost:8888';

// Sal público usado para derivar a chave do cofre: sha256('<salt>:<senha>').
// A senha NÃO fica no bundle; deve bater com PINE_SALT no .env da raiz.
const PINE_SALT = '7c7507a89e00e50b58a5a695456f8ea9';

async function pineVaultKey(password) {
  const bytes = new TextEncoder().encode(`${PINE_SALT}:${password}`);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
}

export function PineDownloadButton({ firebaseUrl = DEFAULT_FIREBASE_URL }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title="Baixar código Pine Script (GEX Walls) atualizado do dia"
        style={{
          background: 'rgba(201, 162, 39, 0.08)',
          border: '1px solid rgba(201, 162, 39, 0.45)',
          borderRadius: '4px',
          padding: '4px 10px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
          fontFamily: 'var(--font-mono)',
          fontSize: '9px',
          fontWeight: 700,
          color: '#EAB308',
          letterSpacing: '0.06em',
          transition: 'all 0.2s',
        }}
        onMouseEnter={e => {
          e.currentTarget.style.background = 'rgba(201, 162, 39, 0.18)';
          e.currentTarget.style.borderColor = '#EAB308';
        }}
        onMouseLeave={e => {
          e.currentTarget.style.background = 'rgba(201, 162, 39, 0.08)';
          e.currentTarget.style.borderColor = 'rgba(201, 162, 39, 0.45)';
        }}
      >
        <span style={{ fontSize: 11 }}>⬇</span>
        PINE GEX
      </button>

      {open && (
        <PineDownloadModal
          firebaseUrl={firebaseUrl}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

export function PineDownloadModal({ firebaseUrl = DEFAULT_FIREBASE_URL, onClose }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pineData, setPineData] = useState(null);
  const [copied, setCopied] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  const triggerBrowserDownload = (content, filename = 'jumba_tradingview.pine') => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setDownloaded(true);
  };

  const fetchAndDownloadPine = async (pwd) => {
    setLoading(true);
    setError('');
    try {
      let data = null;
      const effectiveFbUrl = firebaseUrl || import.meta.env.VITE_FIREBASE_URL;
      const key = await pineVaultKey(pwd);

      // 1. API local (localhost) — valida a chave no servidor
      if (!firebaseUrl && DEFAULT_API) {
        try {
          const res = await fetch(`${DEFAULT_API}/api/gex/pine?key=${key}`);
          if (res.status === 403) throw new Error('Senha incorreta.');
          if (res.ok) {
            const json = await res.json();
            if (json && json.content) data = json;
          }
        } catch (err) {
          if (err.message === 'Senha incorreta.') throw err;
          // API local indisponível: tenta o cofre do Firebase
        }
      }

      // 2. Cofre no Firebase RTDB: /pine_vault/<sha256(salt:senha)>
      //    O caminho só existe para a senha correta; o nó pai não é listável.
      if (!data && effectiveFbUrl) {
        const baseUrl = effectiveFbUrl.replace(/\.json$/, '').replace(/\/$/, '');
        const res = await fetch(`${baseUrl}/pine_vault/${key}.json?t=${Date.now()}`);
        if (res.ok) {
          const json = await res.json();
          if (json && json.content) data = json;
          else throw new Error('Senha incorreta.');
        }
      }

      if (!data || !data.content) {
        throw new Error('Código Pine não encontrado no servidor.');
      }

      setPineData(data);
      triggerBrowserDownload(data.content, data.filename || 'jumba_tradingview.pine');
    } catch (err) {
      setError(err.message || 'Erro ao baixar o arquivo Pine.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = (e) => {
    setPassword(e.target.value);
    setError('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const pwd = password.trim();
    if (!pwd || loading) return;
    fetchAndDownloadPine(pwd);
  };

  const handleCopy = async () => {
    if (!pineData?.content) return;
    try {
      await navigator.clipboard.writeText(pineData.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    } catch (_) {
      const textarea = document.createElement('textarea');
      textarea.value = pineData.content;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0, 0, 0, 0.75)', zIndex: 2000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        backdropFilter: 'blur(4px)',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#0F172A',
          border: '1px solid #334155',
          borderRadius: 12,
          padding: 24,
          minWidth: 360,
          maxWidth: 460,
          width: '90%',
          boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
          fontFamily: 'var(--font-mono)',
          color: '#E2E8F0',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: 18, color: '#EAB308', fontWeight: 500 }}>
              Jumba GEX Walls · TradingView Pine
            </div>
            <div style={{ fontSize: 10, color: '#64748B', marginTop: 2 }}>
              Script diário consolidado (15 ativos)
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', color: '#64748B',
              fontSize: 18, cursor: 'pointer', padding: '4px 8px', lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        {!pineData ? (
          <form onSubmit={handleSubmit}>
            <label style={{ display: 'block', fontSize: 11, color: '#94A3B8', marginBottom: 8 }}>
              Digite a senha de acesso para liberar o download:
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                ref={inputRef}
                type="password"
                inputMode="numeric"
                placeholder="••••"
                value={password}
                onChange={handlePasswordChange}
                style={{
                  flex: 1,
                  background: '#1E293B',
                  border: `1px solid ${error ? '#EF4444' : '#334155'}`,
                  borderRadius: 6,
                  padding: '10px 12px',
                  color: '#F8FAFC',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 16,
                  letterSpacing: '0.25em',
                  textAlign: 'center',
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                disabled={loading}
                style={{
                  background: '#EAB308',
                  color: '#0F172A',
                  border: 'none',
                  borderRadius: 6,
                  padding: '0 18px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: loading ? 'wait' : 'pointer',
                }}
              >
                {loading ? 'BUSCANDO...' : 'BAIXAR'}
              </button>
            </div>
            {error && (
              <div style={{ color: '#F87171', fontSize: 11, marginTop: 8 }}>
                {error}
              </div>
            )}
          </form>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{
              background: 'rgba(74, 222, 128, 0.08)',
              border: '1px solid rgba(74, 222, 128, 0.3)',
              borderRadius: 8,
              padding: '10px 12px',
              fontSize: 11,
            }}>
              <div style={{ color: '#4ADE80', fontWeight: 700, marginBottom: 4 }}>
                ✓ {downloaded ? 'Download iniciado automaticamente!' : 'Código carregado com sucesso!'}
              </div>
              <div style={{ color: '#94A3B8', fontSize: 10 }}>
                Data da coleta: <strong style={{ color: '#E2E8F0' }}>{pineData.date || '-'}</strong> · Atualizado em: <strong style={{ color: '#E2E8F0' }}>{pineData.updated_at || '-'}</strong>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={handleCopy}
                style={{
                  flex: 1,
                  background: copied ? '#10B981' : '#1E293B',
                  border: `1px solid ${copied ? '#10B981' : '#475569'}`,
                  color: copied ? '#0F172A' : '#F8FAFC',
                  borderRadius: 6,
                  padding: '10px 12px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                {copied ? '✓ CÓDIGO COPIADO!' : '📋 COPIAR CÓDIGO PINE'}
              </button>

              <button
                onClick={() => triggerBrowserDownload(pineData.content, pineData.filename || 'jumba_tradingview.pine')}
                style={{
                  background: 'rgba(234, 179, 8, 0.15)',
                  border: '1px solid rgba(234, 179, 8, 0.5)',
                  color: '#EAB308',
                  borderRadius: 6,
                  padding: '10px 14px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                ⬇ .PINE
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

