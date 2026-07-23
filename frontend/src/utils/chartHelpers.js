import { CrosshairMode, LineStyle } from "lightweight-charts";

export const BASE_CHART_OPTIONS = {
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
    minimumWidth: 70,
  },
  leftPriceScale: {
    visible: false,
  },
  autoSize: true,
};
