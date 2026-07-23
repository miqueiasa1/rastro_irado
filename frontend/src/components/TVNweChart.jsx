import { useEffect, useRef, forwardRef, useImperativeHandle, useState } from "react";
import { LineSeries, CandlestickSeries, LineStyle, createSeriesMarkers } from "lightweight-charts";
import BaseLightweightChart from "./BaseLightweightChart";
import { parseTimeToTimestamp } from "../utils/time";

const TVNweChart = forwardRef(({ history = [], walls = [], showGex = false, showMidWalls = false, effectiveDate, selectedTarget, hideXAxis = true, chartType = 'line', showGarchBands = false, garchVolPct = null }, ref) => {
  const baseChartRef = useRef(null);
  const [chartInstance, setChartInstance] = useState(null);
  const seriesRefs = useRef({});
  const hasFittedRef = useRef(false);

  // Reset fitting state when date or target changes
  useEffect(() => {
    hasFittedRef.current = false;
  }, [selectedTarget, effectiveDate]);

  useImperativeHandle(ref, () => ({
    getChart: () => baseChartRef.current?.getChart(),
    getMainSeries: () => seriesRefs.current.winSeries,
  }));

  // Re-create series when chartInstance or chartType changes
  useEffect(() => {
    if (!chartInstance) return;

    // Clean up old series
    const oldRefs = seriesRefs.current;
    if (oldRefs.winSeries) {
      try { chartInstance.removeSeries(oldRefs.winSeries); } catch { /* ignore */ }
    }
    if (oldRefs.nweUpperSeries) {
      try { chartInstance.removeSeries(oldRefs.nweUpperSeries); } catch { /* ignore */ }
    }
    if (oldRefs.nweLowerSeries) {
      try { chartInstance.removeSeries(oldRefs.nweLowerSeries); } catch { /* ignore */ }
    }
    if (oldRefs.nweCenterSeries) {
      try { chartInstance.removeSeries(oldRefs.nweCenterSeries); } catch { /* ignore */ }
    }

    // NWE Upper Band (Red Dashed)
    const nweUpperSeries = chartInstance.addSeries(LineSeries, {
      color: "#F87171",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
    });

    // NWE Lower Band (Green Dashed)
    const nweLowerSeries = chartInstance.addSeries(LineSeries, {
      color: "#4ADE80",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
    });

    // NWE Center Line (Sky Blue Solid)
    const nweCenterSeries = chartInstance.addSeries(LineSeries, {
      color: "#38BDF8",
      lineWidth: 1.5,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
    });

    // Price Line (Top z-index)
    const winSeries = chartType === 'candle'
      ? chartInstance.addSeries(CandlestickSeries, {
          upColor: "#22c55e",
          downColor: "#ef4444",
          borderVisible: false,
          wickUpColor: "#22c55e",
          wickDownColor: "#ef4444",
          crosshairMarkerVisible: true,
          priceLineVisible: false,
        })
      : chartInstance.addSeries(LineSeries, {
          color: "#E2E8F0",
          lineWidth: 1.5,
          crosshairMarkerVisible: true,
          priceLineVisible: false,
        });

    seriesRefs.current = { winSeries, nweUpperSeries, nweLowerSeries, nweCenterSeries, markersApi: null };
  }, [chartInstance, chartType]);

  // Set Data & Markers
  useEffect(() => {
    if (!chartInstance || !history.length) return;

    const { winSeries, nweUpperSeries, nweLowerSeries, nweCenterSeries } = seriesRefs.current;
    if (!winSeries || !nweUpperSeries || !nweLowerSeries || !nweCenterSeries) return;
    
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

    });

    const sortData = (arr) => arr.sort((a, b) => a.time - b.time).filter((v, i, a) => i === 0 || v.time > a[i - 1].time);

    winSeries.setData(sortData(winData));
    nweUpperSeries.setData(sortData(nweUpperData));
    nweLowerSeries.setData(sortData(nweLowerData));
    nweCenterSeries.setData(sortData(nweCenterData));

    // Auto-fit timeline zoom only once per session/target load
    if (!hasFittedRef.current) {
      setTimeout(() => {
        const currentChart = baseChartRef.current?.getChart();
        if (currentChart) {
          currentChart.timeScale().fitContent();
          hasFittedRef.current = true;
        }
      }, 50);
    }
  }, [history, effectiveDate, chartType, chartInstance]);

  // Set GEX Walls
  useEffect(() => {
    const { winSeries } = seriesRefs.current;
    if (!winSeries || !chartInstance) return;

    if (seriesRefs.current.dynamicWalls) {
      seriesRefs.current.dynamicWalls.forEach((line) => {
        try { winSeries.removePriceLine(line); } catch { /* ignore */ }
      });
    }

    const newLines = [];
    if (showGex && Array.isArray(walls)) {
      walls.forEach((w) => {
        if (w.type === "mid_wall" && !showMidWalls) return;

        let lineStyle = w.style === "dashed" ? LineStyle.Dashed : LineStyle.Solid;
        const isWall = w.type === "wall" || w.type === "mid_wall";
        const lineColor = isWall 
          ? (w.type === "mid_wall" ? "#475569" : "#94A3B8") 
          : (w.color || "#00e676");

        const line = winSeries.createPriceLine({
          price: w.price,
          color: lineColor,
          lineWidth: w.width || (w.type === "mid_wall" ? 1 : 2),
          lineStyle,
          axisLabelVisible: false,
          title: "",
        });
        newLines.push(line);
      });
    }
    seriesRefs.current.dynamicWalls = newLines;
  }, [walls, showGex, showMidWalls, chartInstance, chartType]);

  // Set GARCH Volatility Bands
  useEffect(() => {
    const { winSeries } = seriesRefs.current;
    if (!winSeries || !chartInstance) return;

    if (seriesRefs.current.garchLines) {
      seriesRefs.current.garchLines.forEach((line) => {
        try { winSeries.removePriceLine(line); } catch { /* ignore */ }
      });
    }

    const newLines = [];
    const firstValidBar = history.find(d => d.win_open != null && d.win_open > 0);
    const openPrice = firstValidBar ? firstValidBar.win_open : null;

    if (showGarchBands && openPrice && garchVolPct) {
      const vol = garchVolPct / 100;
      const levels = [
        { price: openPrice * (1 + 2 * vol), color: "#EF4444", title: "GARCH +2σ (95%)", style: LineStyle.Solid },
        { price: openPrice * (1 + vol), color: "#F97316", title: "GARCH +1σ (68%)", style: LineStyle.Dashed },
        { price: openPrice * (1 + 0.5 * vol), color: "#EAB308", title: "GARCH +0.5σ (38%)", style: LineStyle.Dashed },
        { price: openPrice * (1 - 0.5 * vol), color: "#8B5CF6", title: "GARCH -0.5σ (38%)", style: LineStyle.Dashed },
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
  }, [history, showGarchBands, garchVolPct, chartInstance, chartType]);

  const chartOptions = {
    rightPriceScale: {
      visible: true,
      borderColor: "#1a2530",
      scaleMargins: { top: 0.15, bottom: 0.15 },
      minimumWidth: 70,
    },
    leftPriceScale: {
      visible: false,
    },
  };

  return (
    <BaseLightweightChart
      ref={baseChartRef}
      hideXAxis={hideXAxis}
      height="240px"
      chartOptions={chartOptions}
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

TVNweChart.displayName = "TVNweChart";
export default TVNweChart;
