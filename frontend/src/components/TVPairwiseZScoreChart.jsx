import { useEffect, useRef, forwardRef, useImperativeHandle, useCallback } from "react";
import { LineSeries, LineStyle } from "lightweight-charts";
import BaseLightweightChart from "./BaseLightweightChart";
import { parseTimeToTimestamp } from "../utils/time";

const TVPairwiseZScoreChart = forwardRef(({ history = [], effectiveDate, hideXAxis = true }, ref) => {
  const baseChartRef = useRef(null);
  const seriesRefs = useRef({});

  useImperativeHandle(ref, () => ({
    getChart: () => baseChartRef.current?.getChart(),
    getMainSeries: () => seriesRefs.current.zSeries,
  }));

  const handleChartCreated = useCallback((chart) => {
    const zSeries = chart.addSeries(LineSeries, {
      color: "#C9A227",
      lineWidth: 1.5,
      priceLineVisible: false,
      crosshairMarkerVisible: true,
      autoscaleInfoProvider: () => ({
        priceRange: {
          minValue: -2.5,
          maxValue: 2.5,
        },
      }),
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

    const zData = [];

    history.forEach((d) => {
      if (!d.time) return;
      const t = parseTimeToTimestamp(effectiveDate, d.time);
      if (t === 0) return;

      const zVal = d.pair_z;
      if (zVal != null && isFinite(zVal)) {
        zData.push({ time: t, value: zVal });
      } else {
        zData.push({ time: t }); // whitespace
      }
    });

    const sortData = (arr) => arr.sort((a, b) => a.time - b.time).filter((v, i, a) => i === 0 || v.time > a[i - 1].time);

    zSeries.setData(sortData(zData));
  }, [history, effectiveDate]);

  return (
    <BaseLightweightChart
      ref={baseChartRef}
      hideXAxis={hideXAxis}
      height="100px"
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
