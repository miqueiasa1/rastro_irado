import { useEffect, useRef, forwardRef, useImperativeHandle, useState } from "react";
import { LineSeries, LineStyle } from "lightweight-charts";
import BaseLightweightChart from "./BaseLightweightChart";
import { parseTimeToTimestamp } from "../utils/time";
import { FACTOR_COLORS } from "../utils/constants";

const TVKalmanWeightsChart = forwardRef(({ history = [], factorKeys = [], effectiveDate, hideXAxis = true }, ref) => {
  const baseChartRef = useRef(null);
  const [chartInstance, setChartInstance] = useState(null);
  const seriesRefs = useRef({});
  const zeroRefLineRef = useRef(null);

  useImperativeHandle(ref, () => ({
    getChart: () => baseChartRef.current?.getChart(),
    getMainSeries: () => {
      const keys = Object.keys(seriesRefs.current);
      return keys.length > 0 ? seriesRefs.current[keys[0]] : null;
    },
  }));

  // Re-create series when factorKeys or chartInstance changes
  useEffect(() => {
    if (!chartInstance || !factorKeys.length) return;

    // Clean up old series
    Object.values(seriesRefs.current).forEach((series) => {
      try {
        chartInstance.removeSeries(series);
      } catch {
        // ignore
      }
    });

    if (zeroRefLineRef.current) {
      try {
        chartInstance.removeSeries(zeroRefLineRef.current);
      } catch {
        // ignore
      }
    }

    // Create a LineSeries for each factor key
    const seriesMap = {};
    factorKeys.forEach((key, idx) => {
      seriesMap[key] = chartInstance.addSeries(LineSeries, {
        color: FACTOR_COLORS[idx % FACTOR_COLORS.length],
        lineWidth: 1.5,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });
    });

    // Zero reference line
    const zeroRefSeries = chartInstance.addSeries(LineSeries, { visible: false });
    zeroRefSeries.createPriceLine({
      price: 0,
      color: "#475569",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: false,
    });

    seriesRefs.current = seriesMap;
    zeroRefLineRef.current = zeroRefSeries;
  }, [chartInstance, factorKeys]);

  // Set weights data when history updates
  useEffect(() => {
    if (!chartInstance || !history.length || !factorKeys.length) return;

    const seriesMap = seriesRefs.current;
    const dataMaps = {};
    factorKeys.forEach((key) => {
      dataMaps[key] = [];
    });

    history.forEach((d) => {
      if (!d.time) return;
      const t = parseTimeToTimestamp(effectiveDate, d.time);
      if (t === 0) return;

      factorKeys.forEach((key) => {
        const val = d[`weight_${key}`];
        if (val != null && isFinite(val)) {
          dataMaps[key].push({ time: t, value: val });
        } else {
          dataMaps[key].push({ time: t }); // whitespace
        }
      });
    });

    const sortData = (arr) => arr.sort((a, b) => a.time - b.time).filter((v, i, a) => i === 0 || v.time > a[i - 1].time);

    factorKeys.forEach((key) => {
      if (seriesMap[key]) {
        seriesMap[key].setData(sortData(dataMaps[key]));
      }
    });
  }, [history, factorKeys, effectiveDate, chartInstance]);

  return (
    <BaseLightweightChart
      ref={baseChartRef}
      hideXAxis={hideXAxis}
      height="140px"
      onChartCreated={setChartInstance}
    >
      {(!history || history.length === 0) && (
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "#0c1218bb", zIndex: 10 }}>
          <span style={{ color: "#4a6070", fontSize: 12, letterSpacing: 1 }}>AGUARDANDO ABERTURA DO MERCADO</span>
        </div>
      )}
    </BaseLightweightChart>
  );
});

TVKalmanWeightsChart.displayName = "TVKalmanWeightsChart";
export default TVKalmanWeightsChart;
