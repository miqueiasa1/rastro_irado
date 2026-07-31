import { useEffect, useRef, forwardRef, useImperativeHandle, useCallback } from "react";
import { LineSeries, LineStyle, createSeriesMarkers } from "lightweight-charts";
import BaseLightweightChart from "./BaseLightweightChart";
import { parseTimeToTimestamp } from "../utils/time";

const TVPairwiseZScoreChart = forwardRef(({
  history = [],
  effectiveDate,
  hideXAxis = true,
  height = "75px",
  showExhaustionContra = true,
  showExhaustionPro = true
}, ref) => {
  const baseChartRef = useRef(null);
  const seriesRefs = useRef({});

  useImperativeHandle(ref, () => ({
    getChart: () => baseChartRef.current?.getChart(),
    getMainSeries: () => seriesRefs.current.zSeries,
  }));

  const handleChartCreated = useCallback((chart) => {
    const zSeries = chart.addSeries(LineSeries, {
      lineWidth: 1.8,
      priceLineVisible: false,
      crosshairMarkerVisible: true,
      autoscaleInfoProvider: (original) => {
        const res = original();
        if (!res) return res;
        return {
          priceRange: {
            minValue: Math.min(-2.5, res.priceRange.minValue),
            maxValue: Math.max(2.5, res.priceRange.maxValue),
          },
        };
      },
    });

    // Reference lines
    zSeries.createPriceLine({
      price: 2.0,
      color: "#F87171",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: true,
      title: "",
    });
    zSeries.createPriceLine({
      price: -2.0,
      color: "#4ADE80",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: true,
      title: "",
    });
    zSeries.createPriceLine({
      price: 0,
      color: "#475569",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: false,
    });

    seriesRefs.current = { zSeries };
  }, []);

  useEffect(() => {
    const chart = baseChartRef.current?.getChart();
    if (!chart || !history.length) return;

    const { zSeries } = seriesRefs.current;
    if (!zSeries) return;

    const getCategoryColor = (val) => {
      if (val <= -2.0) return "#4ADE80"; // verde claro
      if (val < -0.5) return "#15803D";  // verde apagado
      if (val >= 2.0) return "#F87171";  // vermelho claro
      if (val > 0.5) return "#B91C1C";   // vermelho apagado
      return "#64748B";                 // cinza
    };

    const zData = [];
    history.forEach((d) => {
      if (!d.time) return;
      const t = parseTimeToTimestamp(effectiveDate, d.time);
      if (t === 0) return;

      const zVal = d.pair_z;
      if (zVal != null && isFinite(zVal)) {
        zData.push({
          time: t,
          value: zVal,
          color: getCategoryColor(zVal)
        });
      } else {
        zData.push({ time: t }); // whitespace
      }
    });

    const sortData = (arr) => arr.sort((a, b) => a.time - b.time).filter((v, i, a) => i === 0 || v.time > a[i - 1].time);
    zSeries.setData(sortData(zData));
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
      height={height}
      chartOptions={chartOptions}
      onChartCreated={handleChartCreated}
    >
      {(!history || history.length === 0) && (
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "#0c1218bb", zIndex: 10 }}>
          <span style={{ color: "#4a6070", fontSize: 12, letterSpacing: 1 }}>AGUARDANDO ABERTURA DO MERCADO</span>
        </div>
      )}
    </BaseLightweightChart>
  );
});

TVPairwiseZScoreChart.displayName = "TVPairwiseZScoreChart";
export default TVPairwiseZScoreChart;
