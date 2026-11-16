import { useEffect, useRef, forwardRef, useImperativeHandle, useCallback } from "react";
import { LineSeries, LineStyle } from "lightweight-charts";
import BaseLightweightChart from "./BaseLightweightChart";
import { parseTimeToTimestamp } from "../utils/time";
import { isHonestUi } from "../utils/honesty";

// Fase 21A (REQ-U07): com forecast_ui 'on'/'nowcast_only' as linhas 60/40 são só referência
// (o P é leitura do dia, não sinal de compra/venda).
const refLineOptions = (forecastUi) => {
  const honest = isHonestUi(forecastUi);
  return {
    up: { color: honest ? "#334155" : "#4ADE80", title: honest ? "60" : "compra" },
    down: { color: honest ? "#334155" : "#F87171", title: honest ? "40" : "venda" },
  };
};

const TVProbabilityChart = forwardRef(({ history = [], effectiveDate, hideXAxis = true, forecastUi = "off" }, ref) => {
  const baseChartRef = useRef(null);
  const seriesRefs = useRef({});
  const forecastUiRef = useRef(forecastUi);

  useImperativeHandle(ref, () => ({
    getChart: () => baseChartRef.current?.getChart(),
    getMainSeries: () => seriesRefs.current.pUpSeries,
  }));

  const handleChartCreated = useCallback((chart) => {
    // Line: p_up on the right price scale
    const pUpSeries = chart.addSeries(LineSeries, {
      color: "#38BDF8",
      lineWidth: 2,
      lineStyle: LineStyle.Solid,
      priceScaleId: "right",
      crosshairMarkerVisible: true,
      priceLineVisible: false,
    });

    // Reference lines for p_up
    const ref0 = refLineOptions(forecastUiRef.current);
    const upLine = pUpSeries.createPriceLine({
      price: 60,
      color: ref0.up.color,
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: ref0.up.title,
    });
    const downLine = pUpSeries.createPriceLine({
      price: 40,
      color: ref0.down.color,
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: ref0.down.title,
    });
    pUpSeries.createPriceLine({
      price: 50,
      color: "#1E293B",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: false,
    });

    seriesRefs.current = { pUpSeries, upLine, downLine };
  }, []);

  useEffect(() => {
    forecastUiRef.current = forecastUi;
    const { upLine, downLine } = seriesRefs.current;
    if (!upLine || !downLine) return;
    const o = refLineOptions(forecastUi);
    upLine.applyOptions(o.up);
    downLine.applyOptions(o.down);
  }, [forecastUi]);

  useEffect(() => {
    const chart = baseChartRef.current?.getChart();
    if (!chart || !history.length) return;

    const { pUpSeries } = seriesRefs.current;
    if (!pUpSeries) return;

    const pUpData = [];

    history.forEach((d) => {
      if (!d.time) return;
      const t = parseTimeToTimestamp(effectiveDate, d.time);
      if (t === 0) return;

      const pUp = d.p_up_v1 != null ? d.p_up_v1 : d.p_up;

      if (pUp != null && isFinite(pUp)) {
        pUpData.push({ time: t, value: pUp });
      } else {
        pUpData.push({ time: t }); // whitespace
      }
    });

    // Ensure unique time sorting (lightweight charts throws error if not strictly increasing)
    const sortData = (arr) => arr.sort((a, b) => a.time - b.time).filter((v, i, a) => i === 0 || v.time > a[i - 1].time);

    pUpSeries.setData(sortData(pUpData));
  }, [history, effectiveDate]);

  const chartOptions = {
    leftPriceScale: {
      visible: false,
    },
    rightPriceScale: {
      visible: true,
      borderColor: "#1a2530",
      scaleMargins: { top: 0.1, bottom: 0.1 },
      minimumWidth: 70,
    },
  };

  return (
    <BaseLightweightChart
      ref={baseChartRef}
      hideXAxis={hideXAxis}
      height="170px"
      chartOptions={chartOptions}
      onChartCreated={handleChartCreated}
    >

      {(!history || history.length === 0) && (
        <div style={{ position: "absolute", top: 25, left: 0, right: 0, bottom: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "#0c1218bb", zIndex: 10 }}>
          <span style={{ color: "#4a6070", fontSize: 12, letterSpacing: 1 }}>AGUARDANDO ABERTURA DO MERCADO</span>
        </div>
      )}
    </BaseLightweightChart>
  );
});

TVProbabilityChart.displayName = "TVProbabilityChart";
export default TVProbabilityChart;
