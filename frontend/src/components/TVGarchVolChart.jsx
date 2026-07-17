import { useEffect, useRef } from "react";
import { createChart, LineSeries, CrosshairMode } from "lightweight-charts";

export default function TVGarchVolChart({ history = [], forecast = [] }) {
  const containerRef = useRef();
  const chartRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Filter out invalid/empty items
    const chartData = history
      .map(h => ({
        time: h.time,
        value: h.garch_cond_vol_pct
      }))
      .filter(item => item.time && !isNaN(item.value))
      .sort((a, b) => a.time.localeCompare(b.time));

    if (chartData.length === 0) return;

    // Create the chart
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: "solid", color: "#0E0E11" },
        textColor: "#64748B",
        fontSize: 9,
        attributionLogo: false,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { visible: true, labelVisible: true },
        horzLine: { visible: true, labelVisible: true }
      },
      timeScale: {
        visible: true,
        borderColor: "#1E293B",
      },
      rightPriceScale: {
        visible: true,
        borderColor: "#1E293B",
      },
      width: containerRef.current.clientWidth,
      height: 120,
    });

    const volSeries = chart.addSeries(LineSeries, {
      color: "#ffd600",
      lineWidth: 1.5,
      priceLineVisible: false,
    });

    volSeries.setData(chartData);
    chart.timeScale().fitContent();

    chartRef.current = chart;

    const handleResize = () => {
      if (chartRef.current && containerRef.current) {
        chartRef.current.resize(containerRef.current.clientWidth, 120);
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [history]);

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 16, background: "#0E0E11", border: "1px solid #1C1C22", borderRadius: 6, padding: 12, marginTop: 16 }}>
      {/* Chart Section */}
      <div style={{ flex: "1 1 300px", minWidth: 250 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#64748B", marginBottom: 6, letterSpacing: "0.1em", textTransform: "uppercase" }}>
          Histórico Volatilidade Condicional (GARCH)
        </div>
        <div ref={containerRef} style={{ width: "100%", height: 120 }} />
      </div>

      {/* Forecast Section */}
      <div style={{ flex: "0 0 200px", borderLeft: "1px solid #1C1C22", paddingLeft: 16, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#64748B", marginBottom: 8, letterSpacing: "0.1em", textTransform: "uppercase" }}>
            Projeção (5 Dias)
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {forecast.map((f, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-mono)", fontSize: 10, color: "#CBD5E1" }}>
                <span style={{ color: "#64748B" }}>{f.step}:</span>
                <span style={{ fontWeight: 600, color: "#ffd600" }}>{f.vol_forecast_pct.toFixed(3)}%</span>
              </div>
            ))}
            {forecast.length === 0 && (
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#475569" }}>
                Sem projeção disponível.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
