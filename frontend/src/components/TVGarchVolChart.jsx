import { useEffect, useRef, useState } from "react";
import { LineSeries } from "lightweight-charts";
import BaseLightweightChart from "./BaseLightweightChart";

export default function TVGarchVolChart({ history = [], forecast = [] }) {
  const baseChartRef = useRef(null);
  const [chartInstance, setChartInstance] = useState(null);
  const volSeriesRef = useRef(null);

  // Parse and set data when history or series is ready
  useEffect(() => {
    if (!chartInstance) return;

    // Clean up old series
    if (volSeriesRef.current) {
      try {
        chartInstance.removeSeries(volSeriesRef.current);
      } catch {
        // ignore
      }
    }

    const series = chartInstance.addSeries(LineSeries, {
      color: "#ffd600",
      lineWidth: 1.5,
      priceLineVisible: false,
    });

    volSeriesRef.current = series;
  }, [chartInstance]);

  useEffect(() => {
    if (!chartInstance || !volSeriesRef.current || !history.length) return;

    // Filter out invalid/empty items
    const chartData = history
      .map(h => ({
        time: h.time,
        value: h.garch_cond_vol_pct
      }))
      .filter(item => item.time && !isNaN(item.value))
      .sort((a, b) => a.time.localeCompare(b.time));

    if (chartData.length > 0) {
      volSeriesRef.current.setData(chartData);
      if (chartData.length > 100) {
        chartInstance.timeScale().setVisibleLogicalRange({
          from: chartData.length - 100,
          to: chartData.length - 1
        });
      } else {
        chartInstance.timeScale().fitContent();
      }
    }
  }, [history, chartInstance]);

  const formatDate = (time) => {
    if (!time) return "";
    if (typeof time === "string") {
      const parts = time.split("-");
      if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0].slice(-2)}`;
      return time;
    }
    if (typeof time === "object" && time.year) {
      return `${String(time.day).padStart(2, "0")}/${String(time.month).padStart(2, "0")}/${String(time.year).slice(-2)}`;
    }
    if (typeof time === "number") {
      const d = new Date(time * 1000);
      if (!isNaN(d.getTime())) {
        return `${String(d.getUTCDate()).padStart(2, "0")}/${String(d.getUTCMonth() + 1).padStart(2, "0")}/${String(d.getUTCFullYear()).slice(-2)}`;
      }
    }
    return String(time);
  };

  const chartOptions = {
    layout: {
      background: { type: "solid", color: "#0E0E11" },
      textColor: "#64748B",
      fontSize: 9,
      attributionLogo: false,
    },
    localization: {
      timeFormatter: formatDate,
    },
    grid: {
      vertLines: { visible: false },
      horzLines: { visible: false },
    },
    crosshair: {
      vertLine: { visible: true, labelVisible: true },
      horzLine: { visible: true, labelVisible: true }
    },
    timeScale: {
      visible: true,
      borderColor: "#1E293B",
      timeVisible: false,
      tickMarkFormatter: (time) => {
        if (typeof time === "string") {
          const parts = time.split("-");
          if (parts.length === 3) return `${parts[2]}/${parts[1]}`;
        }
        if (typeof time === "object" && time.year) {
          return `${String(time.day).padStart(2, "0")}/${String(time.month).padStart(2, "0")}`;
        }
        if (typeof time === "number") {
          const d = new Date(time * 1000);
          if (!isNaN(d.getTime())) {
            return `${String(d.getUTCDate()).padStart(2, "0")}/${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
          }
        }
        return String(time);
      },
    },
    rightPriceScale: {
      visible: true,
      borderColor: "#1E293B",
    },
  };

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 16, background: "#0E0E11", border: "1px solid #1C1C22", borderRadius: 6, padding: 12, marginTop: 16 }}>
      {/* Chart Section */}
      <div style={{ flex: "1 1 300px", minWidth: 250 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#64748B", marginBottom: 6, letterSpacing: "0.1em", textTransform: "uppercase" }}>
          Histórico Volatilidade Condicional (GARCH)
        </div>
        <BaseLightweightChart
          ref={baseChartRef}
          hideXAxis={false}
          height="120px"
          chartOptions={chartOptions}
          onChartCreated={setChartInstance}
        />
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
