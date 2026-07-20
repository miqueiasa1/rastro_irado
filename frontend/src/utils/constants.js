// Mapa cosmético de labels para fatores conhecidos
export const FACTOR_DISPLAY = {
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
};

// Gera meta de fator dinamicamente a partir da key
export function getFactorMeta(fkey) {
  const known = FACTOR_DISPLAY[fkey];
  if (known) return { label: known.label, icon: known.icon, desc: known.label };
  return { label: fkey.toUpperCase(), icon: '📊', desc: fkey };
}

export const FACTOR_COLORS = [
  '#4ADE80', '#60A5FA', '#FBBF24', '#C084FC',
  '#F87171', '#2DD4BF', '#F472B6', '#A3E635',
  '#FCD34D', '#A78BFA', '#34D399', '#FB923C'
];
