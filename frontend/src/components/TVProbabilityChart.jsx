import { useEffect, useRef, forwardRef, useImperativeHandle, useCallback } from "react";
import { LineSeries, LineStyle } from "lightweight-charts";
import BaseLightweightChart from "./BaseLightweightChart";
import { parseTimeToTimestamp } from "../utils/time";

const TVProbabilityChart = forwardRef(({ history = [], effectiveDate, hideXAxis = true }, ref) => {
  const baseChartRef = useRef(null);
  const seriesRefs = useRef({});

  useImperativeHandle(ref, () => ({
    getChart: () => baseChartRef.current?.getChart(),
    getMainSeries: () => seriesRefs.current.pUpSeries,
  }));

  const handleChartCreated = useCallback((chart) => {
    // Line: p_up on the right price scale
    const pUpSeries = chart.addSeries(LineSeries, {
      color: "#60A5FA",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceScaleId: "right",
      crosshairMarkerVisible: true,
      priceLineVisible: false,
    });

    // Reference lines for p_up
    pUpSeries.createPriceLine({
      price: 60,
      color: "#4ADE80",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: "compra",
    });
    pUpSeries.createPriceLine({
      price: 40,
      color: "#F87171",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: "venda",
    });
    pUpSeries.createPriceLine({
      price: 50,
      color: "#1E293B",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: false,
    });

    seriesRefs.current = { pUpSeries };
  }, []);

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
      minimumWidth: 45,
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
