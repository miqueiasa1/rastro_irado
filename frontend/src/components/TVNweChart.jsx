import { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import { createChart, LineSeries, CandlestickSeries, LineStyle, CrosshairMode, createSeriesMarkers } from "lightweight-charts";

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

const TVNweChart = forwardRef(({ history = [], walls = [], showGex = false, showMidWalls = false, effectiveDate, selectedTarget, hideXAxis = true, chartType = 'line', showGarchBands = false, garchVolPct = null }, ref) => {
  const containerRef = useRef();
  const chartRef = useRef(null);
  const seriesRefs = useRef({});
  const hasFittedRef = useRef(false);

  // Reset fitting state when date or target changes
  useEffect(() => {
    hasFittedRef.current = false;
  }, [selectedTarget, effectiveDate]);

  useImperativeHandle(ref, () => ({
    getChart: () => chartRef.current,
    getMainSeries: () => seriesRefs.current.winSeries,
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
        scaleMargins: { top: 0.15, bottom: 0.15 },
        minimumWidth: 45,
      },
      leftPriceScale: {
        visible: false, // hidden spacer scale
        minimumWidth: 55,
      },
      autoSize: true,
    });

    chartRef.current = chart;

    // NWE Upper Band (Red Dashed)
    const nweUpperSeries = chart.addSeries(LineSeries, {
      color: "#F87171",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
    });

    // NWE Lower Band (Green Dashed)
    const nweLowerSeries = chart.addSeries(LineSeries, {
      color: "#4ADE80",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
    });

    // NWE Center Line (Sky Blue Solid)
    const nweCenterSeries = chart.addSeries(LineSeries, {
      color: "#38BDF8",
      lineWidth: 1.5,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
    });

    // Price Line (Top z-index)
    const winSeries = chartType === 'candle'
      ? chart.addSeries(CandlestickSeries, {
          upColor: "#22c55e",
          downColor: "#ef4444",
          borderVisible: false,
          wickUpColor: "#22c55e",
          wickDownColor: "#ef4444",
          crosshairMarkerVisible: true,
          priceLineVisible: false,
        })
      : chart.addSeries(LineSeries, {
          color: "#E2E8F0",
          lineWidth: 1.5,
          crosshairMarkerVisible: true,
          priceLineVisible: false,
        });

    seriesRefs.current = { winSeries, nweUpperSeries, nweLowerSeries, nweCenterSeries };

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRefs.current = {};
    };
  }, [chartType]);

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.timeScale().applyOptions({ visible: !hideXAxis });
    }
  }, [hideXAxis]);

  // Set Data & Markers
  useEffect(() => {
    if (!chartRef.current || !history.length) return;

    const { winSeries, nweUpperSeries, nweLowerSeries, nweCenterSeries } = seriesRefs.current;
    
    const winData = [];
    const nweUpperData = [];
    const nweLowerData = [];
    const nweCenterData = [];
    
    const markers = [];

    history.forEach((d) => {
      if (!d.time) return;
      const t = parseTimeToTimestamp(effectiveDate, d.time);
      if (t === 0) return;

      // Price Series
      if (chartType === 'candle') {
        const c = d.win_current;
        if (c != null && isFinite(c)) {
          const o = d.win_bar_open != null ? d.win_bar_open : c;
          const h = d.win_high != null ? d.win_high : c;
          const l = d.win_low != null ? d.win_low : c;
          winData.push({ time: t, open: o, high: h, low: l, close: c });
        }
      } else {
        if (d.win_current != null && isFinite(d.win_current)) {
          winData.push({ time: t, value: d.win_current });
        } else {
          winData.push({ time: t });
        }
      }

      // NWE Bands
      if (d.nwe_upper_price != null && isFinite(d.nwe_upper_price)) {
        nweUpperData.push({ time: t, value: d.nwe_upper_price });
      } else {
        nweUpperData.push({ time: t });
      }

      if (d.nwe_lower_price != null && isFinite(d.nwe_lower_price)) {
        nweLowerData.push({ time: t, value: d.nwe_lower_price });
      } else {
        nweLowerData.push({ time: t });
      }

      // Center Line
      if (d.nwe_center_price != null && isFinite(d.nwe_center_price)) {
        const isUp = d.nwe_slope >= 0;
        nweCenterData.push({
          time: t,
          value: d.nwe_center_price,
          color: isUp ? "#4ADE80" : "#F87171"
        });
      } else {
        nweCenterData.push({ time: t });
      }

      // Sinais (Markers)
      // Pair signals (Circles)
      if (d.pair_compra != null && isFinite(d.pair_compra)) {
        const isCounterTrend = d.p_up != null && d.p_up < 45;
        markers.push({
          time: t,
          position: "belowBar",
          shape: "circle",
          color: isCounterTrend ? "rgba(234, 179, 8, 0.45)" : "#4ADE80",
          text: "",
          size: 1.2,
        });
      } else if (d.pair_venda != null && isFinite(d.pair_venda)) {
        const isCounterTrend = d.p_up != null && d.p_up > 55;
        markers.push({
          time: t,
          position: "aboveBar",
          shape: "circle",
          color: isCounterTrend ? "rgba(234, 179, 8, 0.45)" : "#F87171",
          text: "",
          size: 1.2,
        });
      }

      // Z-Score signals (Squares)
      if (d.z_compra_val != null && isFinite(d.z_compra_val)) {
        markers.push({
          time: t,
          position: "belowBar",
          shape: "square",
          color: "#4ADE80",
          text: "",
          size: 1.2,
        });
      } else if (d.z_venda_val != null && isFinite(d.z_venda_val)) {
        markers.push({
          time: t,
          position: "aboveBar",
          shape: "square",
          color: "#F87171",
          text: "",
          size: 1.2,
        });
      }
    });

    const sortData = (arr) => arr.sort((a, b) => a.time - b.time).filter((v, i, a) => i === 0 || v.time > a[i - 1].time);

    winSeries.setData(sortData(winData));
    nweUpperSeries.setData(sortData(nweUpperData));
    nweLowerSeries.setData(sortData(nweLowerData));
    nweCenterSeries.setData(sortData(nweCenterData));

    // Sort markers by time
    markers.sort((a, b) => a.time - b.time);
    if (!seriesRefs.current.markersApi) {
      seriesRefs.current.markersApi = createSeriesMarkers(winSeries, markers);
    } else {
      seriesRefs.current.markersApi.setMarkers(markers);
    }

    // Auto-fit timeline zoom only once per session/target load
    if (!hasFittedRef.current) {
      setTimeout(() => {
        if (chartRef.current) {
          chartRef.current.timeScale().fitContent();
          hasFittedRef.current = true;
        }
      }, 50);
    }
  }, [history, effectiveDate, chartType]);

  // Set GEX Walls
  useEffect(() => {
    const { winSeries } = seriesRefs.current;
    if (!winSeries) return;

    if (seriesRefs.current.dynamicWalls) {
      seriesRefs.current.dynamicWalls.forEach((line) => winSeries.removePriceLine(line));
    }

    const newLines = [];
    if (showGex && Array.isArray(walls)) {
      walls.forEach((w) => {
        if (w.type === "mid_wall" && !showMidWalls) return;

        let lineStyle = w.style === "dashed" ? LineStyle.Dashed : LineStyle.Solid;
        const isNormal = w.type === "wall" || w.type === "mid_wall";
        const line = winSeries.createPriceLine({
          price: w.price,
          color: isNormal ? "#FFFFFF" : w.color,
          lineWidth: w.type === "mid_wall" ? 1 : 2,
          lineStyle,
          axisLabelVisible: false,
          title: "",
        });
        newLines.push(line);
      });
    }
    seriesRefs.current.dynamicWalls = newLines;
  }, [walls, showGex, showMidWalls, chartType]);

  // Set GARCH Volatility Bands
  useEffect(() => {
    const { winSeries } = seriesRefs.current;
    if (!winSeries) return;

    if (seriesRefs.current.garchLines) {
      seriesRefs.current.garchLines.forEach((line) => winSeries.removePriceLine(line));
    }

    const newLines = [];
    const firstValidBar = history.find(d => d.win_open != null && d.win_open > 0);
    const openPrice = firstValidBar ? firstValidBar.win_open : null;

    if (showGarchBands && openPrice && garchVolPct) {
      const vol = garchVolPct / 100;
      const levels = [
        { price: openPrice * (1 + 2 * vol), color: "#EF4444", title: "GARCH +2σ (95%)", style: LineStyle.Solid },
        { price: openPrice * (1 + vol), color: "#F97316", title: "GARCH +1σ (68%)", style: LineStyle.Dashed },
        { price: openPrice * (1 - vol), color: "#10B981", title: "GARCH -1σ (68%)", style: LineStyle.Dashed },
        { price: openPrice * (1 - 2 * vol), color: "#06B6D4", title: "GARCH -2σ (95%)", style: LineStyle.Solid },
      ];

      levels.forEach((lvl) => {
        const line = winSeries.createPriceLine({
          price: lvl.price,
          color: lvl.color,
          lineWidth: 1,
          lineStyle: lvl.style,
          axisLabelVisible: true,
          title: lvl.title,
        });
        newLines.push(line);
      });
    }
    seriesRefs.current.garchLines = newLines;
  }, [history, showGarchBands, garchVolPct, chartType]);

  return (
    <div style={{ background: "#0c1218", borderRadius: hideXAxis ? "0" : "0 0 8px 8px", paddingBottom: 4, position: "relative" }}>
      <div ref={containerRef} style={{ width: "100%", height: "240px" }} />
      {(!history || history.length === 0) && (
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "#0c1218bb", zIndex: 10 }}>
          <span style={{ color: "#4a6070", fontSize: 12, letterSpacing: 1 }}>AGUARDANDO ABERTURA DO MERCADO</span>
        </div>
      )}
    </div>
  );
});

TVNweChart.displayName = "TVNweChart";
export default TVNweChart;
