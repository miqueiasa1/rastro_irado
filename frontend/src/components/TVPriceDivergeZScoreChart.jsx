import { useEffect, useRef, forwardRef, useImperativeHandle, useCallback } from "react";
import { LineSeries, LineStyle, createSeriesMarkers } from "lightweight-charts";
import BaseLightweightChart from "./BaseLightweightChart";
import { parseTimeToTimestamp } from "../utils/time";

const TVPriceDivergeZScoreChart = forwardRef(({
  history = [],
  effectiveDate,
  hideXAxis = true,
  threshold = 2.0,
  height = "75px",
  showExhaustionContra = true,
  showExhaustionPro = true,
  valueKey = "price_diverge_z",
  lineColor = null,
}, ref) => {
  const baseChartRef = useRef(null);
  const seriesRefs = useRef({});
  const priceLinesRef = useRef([]);

  const thresholdRef = useRef(threshold);
  useEffect(() => {
    thresholdRef.current = threshold;
  }, [threshold]);

  useImperativeHandle(ref, () => ({
    getChart: () => baseChartRef.current?.getChart(),
    getMainSeries: () => seriesRefs.current.zSeries,
  }));

  const handleChartCreated = useCallback((chart) => {
    const zSeries = chart.addSeries(LineSeries, {
      lineWidth: 1.8,
      color: lineColor || "#64748B",
      priceLineVisible: false,
      crosshairMarkerVisible: true,
      autoscaleInfoProvider: (original) => {
        const res = original();
        if (!res) return res;
        const minVal = -thresholdRef.current * 1.3;
        const maxVal = thresholdRef.current * 1.3;
        return {
          priceRange: {
            minValue: Math.min(minVal, res.priceRange.minValue),
            maxValue: Math.max(maxVal, res.priceRange.maxValue),
          },
        };
      },
    });

    seriesRefs.current = { zSeries };
  }, []);

  useEffect(() => {
    const { zSeries } = seriesRefs.current;
    if (!zSeries) return;

    // Remove existing price lines
    if (priceLinesRef.current.length > 0) {
      priceLinesRef.current.forEach(line => {
        try {
          zSeries.removePriceLine(line);
        } catch (e) {
          // ignore
        }
      });
    }

    // Create new dynamic price lines based on current threshold
    const line1 = zSeries.createPriceLine({
      price: threshold,
      color: "#F87171",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: true,
      title: "venda",
    });

    const line2 = zSeries.createPriceLine({
      price: -threshold,
      color: "#4ADE80",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: true,
      title: "compra",
    });

    const line3 = zSeries.createPriceLine({
      price: 0,
      color: "#475569",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: false,
    });

    priceLinesRef.current = [line1, line2, line3];
  }, [threshold, seriesRefs.current.zSeries]);

  useEffect(() => {
    const chart = baseChartRef.current?.getChart();
    if (!chart || !history.length) return;

    const { zSeries } = seriesRefs.current;
    if (!zSeries) return;

    const getCategoryColor = (val) => {
      if (val <= -threshold) return "#4ADE80"; // verde claro
      if (val < -0.5) return "#15803D";        // verde apagado
      if (val >= threshold) return "#F87171";  // vermelho claro
      if (val > 0.5) return "#B91C1C";         // vermelho apagado
      return "#64748B";                       // cinza
    };

    const zData = [];
    history.forEach((d) => {
      if (!d.time) return;
      const t = parseTimeToTimestamp(effectiveDate, d.time);
      if (t === 0) return;

      const zVal = d[valueKey] != null ? d[valueKey] : d.price_diverge_z;
      if (zVal != null && isFinite(zVal)) {
        zData.push({
          time: t,
          value: zVal,
          color: lineColor || getCategoryColor(zVal)
        });
      } else {
        zData.push({ time: t }); // whitespace
      }
    });

    const sortData = (arr) => arr.sort((a, b) => a.time - b.time).filter((v, i, a) => i === 0 || v.time > a[i - 1].time);
    zSeries.setData(sortData(zData));
  }, [history, effectiveDate, threshold, valueKey, lineColor]);

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

TVPriceDivergeZScoreChart.displayName = "TVPriceDivergeZScoreChart";
export default TVPriceDivergeZScoreChart;
