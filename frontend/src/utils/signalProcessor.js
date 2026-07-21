/**
 * Utiitário puro de processamento de sinais estatísticos para o IRAI Dashboard.
 * Recebe as barras brutas do NWE/Engine e calcula os marcadores de gráfico e cores do Heatmap (D-P-Z-E).
 */

export function processSeriesSignals(rawNwe, seriesInfo = {}, pairSignalsMemory = { current: {} }, zscoreSignalsMemory = { current: {} }) {
  if (!rawNwe || !Array.isArray(rawNwe)) return [];

  const threshold = seriesInfo.divergence_threshold || 0.75;
  const lastIndex = rawNwe.length - 1;

  return rawNwe.map((entry, index) => {
    const isLiveBar = index === lastIndex;
    const timestampKey = entry.timestamp_utc || entry.time || index;
    const memKey = `${seriesInfo.target || 'target'}_${timestampKey}`;

    const zScore = entry.pair_z !== undefined ? entry.pair_z : (entry.z_score !== undefined ? entry.z_score : 0);
    const pUpDir = entry.p_up != null ? entry.p_up : 50;

    let z_compra = 0;
    let z_venda = 0;
    let pair_compra = undefined;
    let pair_venda = undefined;
    let hm_color_pr = '#1E293B';

    if (zScore != null && isFinite(zScore)) {
      if (zScore <= -2.0) z_compra = entry.win_current;
      else if (zScore >= 2.0) z_venda = entry.win_current;
    }

    const isPairBuy = z_compra > 0;
    const isPairSell = z_venda > 0;

    if (isLiveBar) {
      if (isPairBuy) pairSignalsMemory.current[memKey] = 'buy';
      else if (isPairSell) pairSignalsMemory.current[memKey] = 'sell';
    }

    const activeSignal = isLiveBar ? pairSignalsMemory.current[memKey] : (isPairBuy ? 'buy' : isPairSell ? 'sell' : null);
    if (activeSignal === 'buy') {
      pair_compra = entry.win_current;
      const isCounterTrend = pUpDir < 45;
      hm_color_pr = isCounterTrend ? '#EAB308' : '#4ADE80';
    } else if (activeSignal === 'sell') {
      pair_venda = entry.win_current;
      const isCounterTrend = pUpDir > 55;
      hm_color_pr = isCounterTrend ? '#EAB308' : '#F87171';
    }

    // Z-Score (Quadrado no gráfico) - Apenas quando há divergência real
    const prevEntry = index > 0 ? rawNwe[index - 1] : null;
    const prevZ = prevEntry ? (prevEntry.price_diverge_z || 0) : 0;
    const currZ = entry.price_diverge_z || 0;
    const pUp = entry.p_up != null ? entry.p_up : 50;

    const isZBuyRaw = currZ <= -threshold && (entry.price_diverges || pUp >= 50);
    const isZSellRaw = currZ >= threshold && (entry.price_diverges || pUp <= 50);

    const isZBuy = isZBuyRaw && prevZ > -threshold;
    const isZSell = isZSellRaw && prevZ < threshold;

    if (isLiveBar) {
      if (isZBuy) zscoreSignalsMemory.current[memKey] = 'buy';
      else if (isZSell) zscoreSignalsMemory.current[memKey] = 'sell';
    }

    const activeZSignal = isLiveBar ? zscoreSignalsMemory.current[memKey] : (isZBuy ? 'buy' : isZSell ? 'sell' : null);
    let z_compra_val = undefined;
    let z_venda_val = undefined;
    if (activeZSignal === 'buy') {
      z_compra_val = entry.win_current;
    } else if (activeZSignal === 'sell') {
      z_venda_val = entry.win_current;
    }

    const winReturn = entry.win_return || 0;
    const isNweExhaustionDown = entry.nwe_upper_price !== undefined && entry.nwe_upper_price !== null && entry.win_current !== undefined && entry.win_current !== null && entry.win_current > entry.nwe_upper_price;
    const isNweExhaustionUp = entry.nwe_lower_price !== undefined && entry.nwe_lower_price !== null && entry.win_current !== undefined && entry.win_current !== null && entry.win_current < entry.nwe_lower_price;

    const isBuy = pUp >= 60;
    const isSell = pUp <= 40;

    const isReturnDivergentBuy = isBuy && winReturn < 0;
    const isReturnDivergentSell = isSell && winReturn > 0;
    let hm_color_d = isReturnDivergentBuy ? '#4ADE80' : isReturnDivergentSell ? '#F87171' : '#1E293B';

    const nweUp = entry.nwe_slope !== undefined ? entry.nwe_slope >= 0 : undefined;
    const isNweDivergentBuy = isBuy && nweUp === false;
    const isNweDivergentSell = isSell && nweUp === true;
    let hm_color_p = isNweDivergentBuy ? '#4ADE80' : isNweDivergentSell ? '#F87171' : '#1E293B';

    let hm_color_z = '#1E293B';
    if (isZBuyRaw) {
      hm_color_z = '#4ADE80';
    } else if (isZSellRaw) {
      hm_color_z = '#F87171';
    }

    let hm_color_e = isNweExhaustionUp ? '#4ADE80' : isNweExhaustionDown ? '#F87171' : '#1E293B';

    if (entry.is_ghost) {
      hm_color_d = 'transparent';
      hm_color_p = 'transparent';
      hm_color_z = 'transparent';
      hm_color_e = 'transparent';
      hm_color_pr = 'transparent';
      z_compra = 0;
      z_venda = 0;
      pair_compra = undefined;
      pair_venda = undefined;
      z_compra_val = undefined;
      z_venda_val = undefined;
    }

    return {
      ...entry,
      z_compra,
      z_venda,
      pair_compra,
      pair_venda,
      z_compra_val,
      z_venda_val,
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
