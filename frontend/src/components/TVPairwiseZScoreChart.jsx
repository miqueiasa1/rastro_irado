import { useEffect, useRef, forwardRef, useImperativeHandle, useCallback } from "react";
import { LineSeries, LineStyle, createSeriesMarkers } from "lightweight-charts";
import BaseLightweightChart from "./BaseLightweightChart";
import { parseTimeToTimestamp } from "../utils/time";

const TVPairwiseZScoreChart = forwardRef(({
  history = [],
  effectiveDate,
  hideXAxis = true,
  showExhaustionContra = true,
  showExhaustionPro = true
}, ref) => {
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

    seriesRefs.current = { zSeries, markersApi: null };
  }, []);

  useEffect(() => {
    const chart = baseChartRef.current?.getChart();
    if (!chart || !history.length) return;

    const { zSeries } = seriesRefs.current;
    if (!zSeries) return;

    const zData = [];
    const markers = [];

    history.forEach((d, idx) => {
      if (!d.time) return;
      const t = parseTimeToTimestamp(effectiveDate, d.time);
      if (t === 0) return;

      const zVal = d.pair_z;
      if (zVal != null && isFinite(zVal)) {
        zData.push({ time: t, value: zVal });
      } else {
        zData.push({ time: t }); // whitespace
      }

      // Check pair spread markers (Apenas na entrada/crossover da zona de exaustão)
      const prevZ = idx > 0 ? history[idx - 1]?.pair_z : null;

      const isBuy = (d.pair_compra != null && isFinite(d.pair_compra)) || 
                    (zVal != null && zVal <= -2.0 && (prevZ == null || prevZ > -2.0));
      const isSell = (d.pair_venda != null && isFinite(d.pair_venda)) || 
                     (zVal != null && zVal >= 2.0 && (prevZ == null || prevZ < 2.0));

      if (isBuy || isSell) {
        const pUp = d.p_up != null ? d.p_up : 50;
        const isCounterTrend = isBuy ? (pUp < 45) : (pUp > 55);

        if (isCounterTrend && showExhaustionContra) {
          markers.push({
            time: t,
            position: isBuy ? "belowBar" : "aboveBar",
            shape: "circle",
            color: "#EAB308", // Yellow (Contra o P Dinâmico)
            text: "",
            size: 0.9,
          });
        } else if (!isCounterTrend && showExhaustionPro) {
          markers.push({
            time: t,
            position: isBuy ? "belowBar" : "aboveBar",
            shape: "circle",
            color: isBuy ? "#4ADE80" : "#F87171", // Green or Red (A Favor do P Dinâmico)
            text: "",
            size: 0.9,
          });
        }
      }
    });

    const sortData = (arr) => arr.sort((a, b) => a.time - b.time).filter((v, i, a) => i === 0 || v.time > a[i - 1].time);

    zSeries.setData(sortData(zData));

    markers.sort((a, b) => a.time - b.time);
    if (!seriesRefs.current.markersApi) {
      seriesRefs.current.markersApi = createSeriesMarkers(zSeries, markers);
    } else {
      seriesRefs.current.markersApi.setMarkers(markers);
    }
  }, [history, effectiveDate, showExhaustionContra, showExhaustionPro]);

  const chartOptions = {
    leftPriceScale: {
      visible: false,
    },
    rightPriceScale: {
      visible: true,
      borderColor: "#1a2530",
      scaleMargins: { top: 0.2, bottom: 0.2 },
      minimumWidth: 70,
    },
  };

  return (
    <BaseLightweightChart
      ref={baseChartRef}
      hideXAxis={hideXAxis}
      height="100px"
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

TVPairwiseZScoreChart.displayName = "TVPairwiseZScoreChart";
export default TVPairwiseZScoreChart;
