/**
 * Calcula a convicção do sinal aplicando a calibração por Shrinkage.
 */
export function calculateConviction(pUp, accuracy, isPreview = false, signalColor = '#94A3B8', defaultWeakColor = '#475569') {
  const acc = Math.min(Math.max(accuracy, 50), 100);
  const shrinkFactor = (2 * acc / 100) - 1;
  const pShrunk = 50 + (pUp - 50) * shrinkFactor;
  const conviction = Math.round(Math.abs(pShrunk - 50) * 2);
  const maxConviction = Math.round((acc - 50) * 2);
  const convRatio = maxConviction > 0 ? conviction / maxConviction : 0;
  
  const convLabel = isPreview ? 'pré-mercado' : convRatio >= 0.55 ? 'forte' : convRatio >= 0.25 ? 'moderada' : 'fraca';
  const convColor = isPreview ? '#EAB308' : convRatio >= 0.55 ? signalColor : convRatio >= 0.25 ? '#C9A227' : defaultWeakColor;

  return { conviction, convRatio, convLabel, convColor };
}

/**
 * Avalia a estabilidade do sinal com base nas últimas 8 barras de probabilidade.
 */
export function calculateStability(recentPUp) {
  let stability = 'sem dados';
  let stabilityIcon = '○';
  let stabilityColor = '#334155';
  let stabilityTip = '';

  if (recentPUp.length >= 4) {
    const vals = recentPUp.slice(-8);
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
    const std = Math.sqrt(vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length);

    const hasCross = vals.some(v => v > 50) && vals.some(v => v < 50);

    const half = Math.floor(vals.length / 2);
    const early = vals.slice(0, half).reduce((a, b) => a + b, 0) / half;
    const late = vals.slice(half).reduce((a, b) => a + b, 0) / (vals.length - half);
    const trending = Math.abs(late - early) > 6;

    if (hasCross || std > 18) {
      stability = 'oscilando';
      stabilityIcon = '⟆';
      stabilityColor = '#FBBF24';
      stabilityTip = `Sinal instável — P(↑) cruzou o neutro nas últimas ${vals.length} barras (σ=${std.toFixed(1)}pp). Aguarde confirmação.`;
    } else if (trending && std > 6) {
      stability = 'formando';
      stabilityIcon = '◈';
      stabilityColor = '#60A5FA';
      stabilityTip = `Sinal em formação — ${late > early ? 'ganhando' : 'perdendo'} convicção nas últimas ${vals.length} barras (σ=${std.toFixed(1)}pp).`;
    } else if (std <= 6) {
      stability = 'estável';
      stabilityIcon = '▬';
      stabilityColor = '#4ADE80';
      stabilityTip = `Sinal estável — baixa variação nas últimas ${vals.length} barras (σ=${std.toFixed(1)}pp).`;
    } else {
      stability = 'variando';
      stabilityIcon = '~';
      stabilityColor = '#94A3B8';
      stabilityTip = `Variação moderada (σ=${std.toFixed(1)}pp).`;
    }
  }

  return { stability, stabilityIcon, stabilityColor, stabilityTip };
}
