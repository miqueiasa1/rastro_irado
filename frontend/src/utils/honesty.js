/**
 * Fase 17 — honestidade do painel.
 *
 * Quando `forecast_ui` do alvo é 'on' ou 'nowcast_only', o painel:
 *  - não transforma z de spread/par/macro em COMPRA/VENDA (o z do par não é um z verdadeiro e
 *    não teve vantagem líquida de custos na auditoria); mostra só a posição descritiva;
 *  - não usa a acurácia in-sample para "encolher" a convicção nem a exibe no card;
 *  - rotula o P(↑) como leitura do dia (nowcast), não como previsão.
 * Com 'off' (padrão) nada muda.
 */
export const HONEST_UI_MODES = ['on', 'nowcast_only'];

export function isHonestUi(forecastUi) {
  return HONEST_UI_MODES.includes(forecastUi);
}

const NEUTRAL = '#94A3B8';
const MILD = '#CBD5E1';
const STRONG = '#F59E0B';

/** Rótulo descritivo de um z (posição em relação à referência), sem direção de operação. */
export function describeZ(z, { short = false } = {}) {
  if (z == null || Number.isNaN(z)) return { label: short ? 'N/A' : 'SEM DADOS', color: '#64748B' };
  const a = Math.abs(z);
  if (a >= 2.0) return { label: z > 0 ? (short ? 'BEM ACIMA' : 'BEM ACIMA DA REF.') : (short ? 'BEM ABAIXO' : 'BEM ABAIXO DA REF.'), color: STRONG };
  if (a > 0.5) return { label: z > 0 ? (short ? 'ACIMA' : 'ACIMA DA REF.') : (short ? 'ABAIXO' : 'ABAIXO DA REF.'), color: MILD };
  return { label: short ? 'NA REF.' : 'PRÓXIMO DA REF.', color: NEUTRAL };
}

/** Rótulo do P(↑) do nowcast: descreve o dia até agora, não é recomendação. */
export function describeNowcast(pUp) {
  if (pUp == null) return { label: 'SEM DADOS', color: '#64748B' };
  if (pUp >= 60) return { label: 'DIA EM ALTA', color: '#4ADE80' };
  if (pUp <= 40) return { label: 'DIA EM BAIXA', color: '#F87171' };
  return { label: 'DIA INDEFINIDO', color: NEUTRAL };
}
