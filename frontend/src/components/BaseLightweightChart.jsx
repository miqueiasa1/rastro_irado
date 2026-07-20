import { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import { createChart } from "lightweight-charts";
import { BASE_CHART_OPTIONS } from "../utils/chartHelpers";

const BaseLightweightChart = forwardRef(({ hideXAxis, height = "100px", children, chartOptions = {}, onChartCreated }, ref) => {
  const containerRef = useRef();
  const chartRef = useRef(null);

  useImperativeHandle(ref, () => ({
    getChart: () => chartRef.current,
  }));

  useEffect(() => {
    if (!containerRef.current) return;

    // Deep merge layout, crosshair, and timescales to preserve defaults while allowing custom settings
    const mergedOptions = {
      ...BASE_CHART_OPTIONS,
      ...chartOptions,
      layout: {
        ...BASE_CHART_OPTIONS.layout,
        ...chartOptions.layout,
      },
      crosshair: {
        ...BASE_CHART_OPTIONS.crosshair,
        ...chartOptions.crosshair,
      },
      timeScale: {
        ...BASE_CHART_OPTIONS.timeScale,
        ...chartOptions.timeScale,
        visible: !hideXAxis,
      },
      rightPriceScale: {
        ...BASE_CHART_OPTIONS.rightPriceScale,
        ...chartOptions.rightPriceScale,
      },
      leftPriceScale: {
        ...BASE_CHART_OPTIONS.leftPriceScale,
        ...chartOptions.leftPriceScale,
      },
    };

    const chart = createChart(containerRef.current, mergedOptions);
    chartRef.current = chart;

    if (onChartCreated) {
      onChartCreated(chart);
    }

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, []); // Run once on mount

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.timeScale().applyOptions({ visible: !hideXAxis });
    }
  }, [hideXAxis]);

  return (
    <div style={{ background: chartOptions?.layout?.background?.color || "#0c1218", borderRadius: hideXAxis ? "0" : "0 0 8px 8px", paddingBottom: 4, position: "relative" }}>
      <div ref={containerRef} style={{ width: "100%", height }} />
      {children}
    </div>
  );
});

BaseLightweightChart.displayName = "BaseLightweightChart";
export default BaseLightweightChart;
