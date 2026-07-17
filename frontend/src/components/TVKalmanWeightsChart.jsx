import { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import { createChart, LineSeries, LineStyle, CrosshairMode } from "lightweight-charts";

const FACTOR_COLORS = [
  "#4ADE80", "#60A5FA", "#FBBF24", "#C084FC",
  "#F87171", "#2DD4BF", "#F472B6", "#A3E635",
  "#FCD34D", "#A78BFA", "#34D399", "#FB923C"
];

function parseTimeToTimestamp(dateStr, timeStr) {
  if (!timeStr) return 0;
  let year = 2026, month = 6, day = 26;
  if (dateStr && dateStr.includes("-")) {
    const parts = dateStr.split("-").map(Number);
    if (parts.length === 3 && !parts.some(isNaN)) {
      [year, month, day] = parts;
    }
  }
  const [hour, minute] = timeStr.split(":").map(Number);
  if (isNaN(hour) || isNaN(minute)) return 0;
  return Math.floor(Date.UTC(year, month - 1, day, hour, minute) / 1000);
}

const TVKalmanWeightsChart = forwardRef(({ history = [], factorKeys = [], effectiveDate, hideXAxis = true }, ref) => {
  const containerRef = useRef();
  const chartRef = useRef(null);
  const seriesRefs = useRef({});

  useImperativeHandle(ref, () => ({
    getChart: () => chartRef.current,
    getMainSeries: () => {
      const keys = Object.keys(seriesRefs.current);
      return keys.length > 0 ? seriesRefs.current[keys[0]] : null;
    },
  }));

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: "solid", color: "#0c1218" },
        textColor: "#4a6070",
        fontSize: 9,
        attributionLogo: false,
      },
      localization: {
        timeFormatter: (time) => {
          const d = new Date(time * 1000);
          return String(d.getUTCHours()).padStart(2, "0") + ":" + String(d.getUTCMinutes()).padStart(2, "0");
        },
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#c8a444", width: 1, style: LineStyle.Solid, labelBackgroundColor: "#c8a444" },
        horzLine: { visible: false, labelVisible: true, labelBackgroundColor: "#c8a444" },
      },
      timeScale: {
        visible: !hideXAxis,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 15,
        tickMarkFormatter: (time) => {
          const d = new Date(time * 1000);
          return String(d.getUTCHours()).padStart(2, "0") + ":" + String(d.getUTCMinutes()).padStart(2, "0");
        },
      },
      rightPriceScale: {
        visible: true,
        borderColor: "#1a2530",
        autoScale: true,
        minimumWidth: 45,
      },
      leftPriceScale: {
        visible: false, // hidden spacer
        minimumWidth: 55,
      },
      autoSize: true,
    });

    chartRef.current = chart;

    // Create a LineSeries for each factor key
    const seriesMap = {};
    factorKeys.forEach((key, idx) => {
      seriesMap[key] = chart.addSeries(LineSeries, {
        color: FACTOR_COLORS[idx % FACTOR_COLORS.length],
        lineWidth: 1.5,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });
    });

    // Zero reference line
    const firstSeries = chart.addSeries(LineSeries, { visible: false }); // hidden dummy to add reference line to
    firstSeries.createPriceLine({
      price: 0,
      color: "#475569",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: false,
    });

    seriesRefs.current = seriesMap;

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [factorKeys]);

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.timeScale().applyOptions({ visible: !hideXAxis });
    }
  }, [hideXAxis]);

  useEffect(() => {
    if (!chartRef.current || !history.length || !factorKeys.length) return;

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
  }, [history, factorKeys, effectiveDate]);

  return (
    <div style={{ background: "#0c1218", borderRadius: hideXAxis ? "0" : "0 0 8px 8px", paddingBottom: 4, position: "relative" }}>
      <div ref={containerRef} style={{ width: "100%", height: "140px" }} />
      {(!history || history.length === 0) && (
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "#0c1218bb", zIndex: 10 }}>
          <span style={{ color: "#4a6070", fontSize: 12, letterSpacing: 1 }}>AGUARDANDO ABERTURA DO MERCADO</span>
        </div>
      )}
    </div>
  );
});

TVKalmanWeightsChart.displayName = "TVKalmanWeightsChart";
export default TVKalmanWeightsChart;
