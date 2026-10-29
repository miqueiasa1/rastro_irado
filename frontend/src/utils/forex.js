/**
 * Utilitário de identificação de pares Forex.
 */

export const MAJOR_FOREX_CURRENCIES = ["USD", "EUR", "GBP", "CHF", "JPY", "AUD", "CAD", "NZD"];

export function isForexTarget(target) {
  if (!target || typeof target !== 'string') return false;
  const t = target.toUpperCase().trim();
  if (t.length === 6) {
    const base = t.slice(0, 3);
    const quote = t.slice(3);
    return MAJOR_FOREX_CURRENCIES.includes(base) && MAJOR_FOREX_CURRENCIES.includes(quote) && base !== quote;
  }
  return false;
}
