/**
 * Utilitário puro de processamento de sinais estatísticos para o IRAI Dashboard.
 * Recebe as barras brutas do NWE/Engine e calcula os marcadores de gráfico, confluência unificada e Heatmap (D-P-Z-E).
 */

export function processSeriesSignals(rawNwe, seriesInfo = {}, pairSignalsMemory = { current: {} }, zscoreSignalsMemory = { current: {} }) {
  if (!rawNwe || !Array.isArray(rawNwe)) return [];

  const threshold = seriesInfo.divergence_threshold || 2.0;
  const lastIndex = rawNwe.length - 1;

  return rawNwe.map((entry, index) => {
    const isLiveBar = index === lastIndex;
    const timestampKey = entry.timestamp_utc || entry.time || index;
    const memKey = `${seriesInfo.target || 'target'}_${timestampKey}`;

    const pUp = entry.p_up != null ? entry.p_up : 50;
    const currentPrice = entry.win_current;
    const upper = entry.nwe_upper_price;
    const lower = entry.nwe_lower_price;
    const center = entry.nwe_center_price;
    const nweSlope = entry.nwe_slope || 0;
    const nweUp = nweSlope >= 0;

    // 1) Cálculo da Posição Relativa no Envelope NWE
    let nwePosPct = 50;
    if (currentPrice != null && upper != null && lower != null && upper !== lower) {
      nwePosPct = ((currentPrice - lower) / (upper - lower)) * 100;
    }

    const isNweExhaustionDown = upper != null && currentPrice != null && currentPrice > upper;
    const isNweExhaustionUp = lower != null && currentPrice != null && currentPrice < lower;

    // 2) Sinal Unificado: Rastro Macro + Bandas NWE
    let unifiedSignal = "neutral";
    let unifiedColor = "#94A3B8";

    const isRastroBuy = pUp >= 60;
    const isRastroSell = pUp <= 40;

    if (isRastroBuy) {
      if (isNweExhaustionDown || nwePosPct > 90) {
        unifiedSignal = "exhaustion_top";
        unifiedColor = "#F59E0B"; // Alerta topo esticado
      } else if (nwePosPct <= 35) {
        unifiedSignal = "strong_buy";
        unifiedColor = "#10B981"; // Compra forte no fundo/desconto
      } else {
        unifiedSignal = "trend_buy";
        unifiedColor = "#4ADE80"; // Seguir tendência de alta no canal
      }
    } else if (isRastroSell) {
      if (isNweExhaustionUp || nwePosPct < 10) {
        unifiedSignal = "exhaustion_bottom";
        unifiedColor = "#F59E0B"; // Alerta fundo esticado
      } else if (nwePosPct >= 65) {
        unifiedSignal = "strong_sell";
        unifiedColor = "#EF4444"; // Venda forte no topo/prêmio
      } else {
        unifiedSignal = "trend_sell";
        unifiedColor = "#F87171"; // Seguir tendência de baixa no canal
      }
    }

    // 3) Gatilhos de Entrada no Gráfico (Compra / Venda com Timing NWE)
    let pair_compra = undefined;
    let pair_venda = undefined;

    if (unifiedSignal === "strong_buy" || (unifiedSignal === "trend_buy" && currentPrice != null && center != null && currentPrice <= center)) {
      pair_compra = currentPrice;
    } else if (unifiedSignal === "strong_sell" || (unifiedSignal === "trend_sell" && currentPrice != null && center != null && currentPrice >= center)) {
      pair_venda = currentPrice;
    }

    // 4) Heatmap e Alertas
    const winReturn = entry.win_return || 0;
    const isReturnDivergentBuy = isRastroBuy && winReturn < 0;
    const isReturnDivergentSell = isRastroSell && winReturn > 0;
    let hm_color_d = isReturnDivergentBuy ? '#4ADE80' : isReturnDivergentSell ? '#F87171' : '#1E293B';

    const isNweDivergentBuy = isRastroBuy && nweUp === false;
    const isNweDivergentSell = isRastroSell && nweUp === true;
    let hm_color_p = isNweDivergentBuy ? '#4ADE80' : isNweDivergentSell ? '#F87171' : '#1E293B';

    let hm_color_z = '#1E293B';
    const currZ = entry.price_diverge_z || 0;
    if (currZ <= -threshold) hm_color_z = '#4ADE80';
    else if (currZ >= threshold) hm_color_z = '#F87171';

    let hm_color_e = isNweExhaustionUp ? '#4ADE80' : isNweExhaustionDown ? '#F87171' : '#1E293B';
    let hm_color_pr = unifiedColor;

    if (entry.is_ghost) {
      hm_color_d = 'transparent';
      hm_color_p = 'transparent';
      hm_color_z = 'transparent';
      hm_color_e = 'transparent';
      hm_color_pr = 'transparent';
      pair_compra = undefined;
      pair_venda = undefined;
    }

    return {
      ...entry,
      nwePosPct,
      unifiedSignal,
      unifiedColor,
      pair_compra,
      pair_venda,
      z_compra: pair_compra ? currentPrice : 0,
      z_venda: pair_venda ? currentPrice : 0,
      hm_color_d,
      hm_color_p,
      hm_color_z,
      hm_color_e,
      hm_color_pr,
      isNweExhaustionDown,
      isNweExhaustionUp,
    };
  });
}
