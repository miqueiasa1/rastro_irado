import { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import { createChart, LineSeries, LineStyle, CrosshairMode } from "lightweight-charts";

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

const TVProbabilityChart = forwardRef(({ history = [], effectiveDate, selectedTarget, hideXAxis = true }, ref) => {
  const containerRef = useRef();
  const chartRef = useRef(null);
  const seriesRefs = useRef({});

  useImperativeHandle(ref, () => ({
    getChart: () => chartRef.current,
    getMainSeries: () => seriesRefs.current.pUpSeries,
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
      leftPriceScale: {
        visible: false,
      },
      rightPriceScale: {
        visible: true,
        borderColor: "#1a2530",
        scaleMargins: { top: 0.1, bottom: 0.1 },
        minimumWidth: 45,
      },
      autoSize: true,
    });

    chartRef.current = chart;



    // Line 2: p_up on the right price scale
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

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.timeScale().applyOptions({ visible: !hideXAxis });
    }
  }, [hideXAxis]);

  useEffect(() => {
    if (!chartRef.current || !history.length) return;

    const { pUpSeries } = seriesRefs.current;
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

  return (
    <div style={{ background: "#0c1218", borderRadius: hideXAxis ? "0" : "0 0 8px 8px", paddingBottom: 4, position: "relative" }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 14, padding: "6px 12px 2px",
        paddingLeft: 55, borderTop: "1px solid #1a2530", flexWrap: "wrap",
      }}>
        <span style={{ fontSize: 9, fontWeight: "bold", color: "#6f8a9c", letterSpacing: 2 }}>P(↑) DINÂMICO</span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ display: "inline-block", width: 14, height: 2, background: "#60A5FA", borderTop: "1px dashed #60A5FA", borderRadius: 1 }} />
          <span style={{ fontSize: 9, color: "#60A5FA" }}>P(↑) Dinâmico</span>
        </span>
      </div>
      <div ref={containerRef} style={{ width: "100%", height: "170px" }} />
      {(!history || history.length === 0) && (
        <div style={{ position: "absolute", top: 25, left: 0, right: 0, bottom: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "#0c1218bb", zIndex: 10 }}>
          <span style={{ color: "#4a6070", fontSize: 12, letterSpacing: 1 }}>AGUARDANDO ABERTURA DO MERCADO</span>
        </div>
      )}
    </div>
  );
});

TVProbabilityChart.displayName = "TVProbabilityChart";
export default TVProbabilityChart;
