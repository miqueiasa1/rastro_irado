# Phase 3 Research: Refatoração do Frontend React

Este documento apresenta a avaliação técnica e o design de implementação para as 6 melhorias estruturais sugeridas no frontend do dashboard IRAI, visando reduzir a complexidade cognitiva, duplicações de código e melhorar a testabilidade das funções de negócio.

---

## Standard Stack

*   **React (v18+)**: Framework SPA principal.
*   **lightweight-charts (v4.x)**: Biblioteca da TradingView para renderização de gráficos financeiros de alta performance.
*   **Recharts**: Biblioteca usada para o layout secundário e elementos de histórico.
*   **Vanilla CSS**: Estilização do painel e animações de glow.

---

## Architecture Patterns

### 1. Separação Estrita de Responsabilidades (UI vs Lógica)
*   **Lógica de Sinal (Math Pura)**: Toda a matemática financeira, calibração de convicção por *shrinkage* e análise de estabilidade baseada em desvio padrão das séries temporais residirão isoladas do React em `src/utils/signalAnalyzer.js`.
*   **Custom Hook de Dados (`useIraiData`)**: Abstrai as operações de I/O, REST polling, tratamento de erros, cache e mapeamento de séries. `App.jsx` e `Overview.jsx` apenas consomem o estado resolvido pelo hook.
*   **Componentes de Visualização Puro**: Componentes como `SignalGauge.jsx` e os gráficos TradingView apenas recebem dados estruturados via props e renderizam a UI correspondente.

### 2. Wrapper Base para Lightweight Charts
*   Para eliminar a duplicação na inicialização dos canvas, criamos o componente `BaseLightweightChart.jsx` que gerencia o elemento DOM `div`, cria/destrói a instância do `createChart` do Lightweight Charts, manipula o redimensionamento e sincroniza a visibilidade do `timeScale`.
*   As configurações estéticas fundamentais (cor de fundo `#0c1218` ou `#0E0E11`, crosshairs dourados `#c8a444`, bordas das escalas `#1a2530`, etc.) são extraídas para `BASE_CHART_OPTIONS` em `src/utils/chartHelpers.js`.

---

## Don't Hand-Roll

*   **Não reimplementar controle de estado de zoom/pan horizontal**: A sincronização e preservação de zoom deve continuar utilizando `setVisibleLogicalRange` e `LogicalRange` expostos nativamente pelo Lightweight Charts, coordenados via refs no componente pai `App.jsx` para evitar loops infinitos.
*   **Não reimplementar formatação de timezone complexo**: As conversões de fuso horário local e UTC devem permanecer centralizadas e simples em `src/utils/time.js` com suporte a offsets fixos.

---

## Common Pitfalls

1.  **Loops infinitos de sincronização de zoom**: Ao sincronizar o zoom horizontal dos gráficos em tempo real, se as chamadas de alteração dispararem eventos circulares, a página pode travar.
    *   *Mitigação*: Utilizar uma flag de controle mútua `isSyncingRef.current` que atua como semáforo durante as atualizações sincronizadas de Logical Range.
2.  **Reset indesejado de zoom e panning pelo polling**: A atualização de dados a cada 60 segundos não deve resetar o range visível que o usuário está manipulando.
    *   *Mitigação*: Analisar se a borda direita do gráfico está visível usando `logicalRange.to >= prevValidCount - 2` antes de rolar o gráfico para novos dados; caso contrário, manter a posição estática.
3.  **Gráfico de Pair Spread sumindo para Mini Índice**: O `TVPairwiseZScoreChart` deve ser renderizado mesmo em períodos sem dados ou em pré-mercado quando o ativo selecionado for `WIN$N`.
    *   *Mitigação*: A visibilidade do gráfico de Pair Spread deve depender exclusivamente do ativo alvo (`selectedTarget === 'WIN$N'`) e não de dados dinâmicos do array.

---

## Code Examples

### 1. Centralização Matemática: `src/utils/signalAnalyzer.js`
```javascript
/**
 * Calcula a convicção do sinal aplicando a calibração por Shrinkage.
 */
export function calculateConviction(pUp, accuracy, isPreview = false, signalColor = '#94A3B8') {
  const acc = Math.min(Math.max(accuracy, 50), 100);
  const shrinkFactor = (2 * acc / 100) - 1;
  const pShrunk = 50 + (pUp - 50) * shrinkFactor;
  const conviction = Math.round(Math.abs(pShrunk - 50) * 2);
  const maxConviction = Math.round((acc - 50) * 2);
  const convRatio = maxConviction > 0 ? conviction / maxConviction : 0;
  
  const convLabel = isPreview ? 'pré-mercado' : convRatio >= 0.55 ? 'forte' : convRatio >= 0.25 ? 'moderada' : 'fraca';
  const convColor = isPreview ? '#EAB308' : convRatio >= 0.55 ? signalColor : convRatio >= 0.25 ? '#C9A227' : '#475569';

  return { conviction, convRatio, convLabel, convColor };
}

/**
 * Avalia a estabilidade do sinal com base nas últimas 8 barras de probabilidade.
 */
export function calculateStability(recentPUp) {
  let stability = 'sem dados';
  let stabilityIcon = '○';
  let stabilityColor = '#334155';
  let stabilityTip = '';

  if (recentPUp.length >= 4) {
    const vals = recentPUp.slice(-8);
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
    const std = Math.sqrt(vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length);

    const hasCross = vals.some(v => v > 50) && vals.some(v => v < 50);

    const half = Math.floor(vals.length / 2);
    const early = vals.slice(0, half).reduce((a, b) => a + b, 0) / half;
    const late = vals.slice(half).reduce((a, b) => a + b, 0) / (vals.length - half);
    const trending = Math.abs(late - early) > 6;

    if (hasCross || std > 18) {
      stability = 'oscilando';
      stabilityIcon = '⟆';
      stabilityColor = '#FBBF24';
      stabilityTip = `Sinal instável — P(↑) cruzou o neutro nas últimas \${vals.length} barras (σ=\${std.toFixed(1)}pp). Aguarde confirmação.`;
    } else if (trending && std > 6) {
      stability = 'formando';
      stabilityIcon = '◈';
      stabilityColor = '#60A5FA';
      stabilityTip = `Sinal em formação — \${late > early ? 'ganhando' : 'perdendo'} convicção nas últimas \${vals.length} barras (σ=\${std.toFixed(1)}pp).`;
    } else if (std <= 6) {
      stability = 'estável';
      stabilityIcon = '▬';
      stabilityColor = '#4ADE80';
      stabilityTip = `Sinal estável — baixa variação nas últimas \${vals.length} barras (σ=\${std.toFixed(1)}pp).`;
    } else {
      stability = 'variando';
      stabilityIcon = '~';
      stabilityColor = '#94A3B8';
      stabilityTip = `Variação moderada (σ=\${std.toFixed(1)}pp).`;
    }
  }

  return { stability, stabilityIcon, stabilityColor, stabilityTip };
}
```

### 2. Custom Hook: `src/hooks/useIraiData.js`
```javascript
import { useState, useEffect, useCallback, useRef } from "react";
import GEX_LEVELS from "../gexLevels";
import { toLocalTime } from "../utils/time";

const FIREBASE_URL = import.meta.env.VITE_FIREBASE_URL;
const API = FIREBASE_URL ? null : 'http://localhost:8888';

export function useIraiData({ selectedTarget, liveMode, timeframe, selectedDate }) {
  const [dates, setDates] = useState([]);
  const [targetsMeta, setTargetsMeta] = useState([]);
  const [series, setSeries] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const [gexWalls, setGexWalls] = useState([]);
  const [availableRuns, setAvailableRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [garchData, setGarchData] = useState(null);
  const [seriesInfo, setSeriesInfo] = useState({});
  
  const isFirstLoadRef = useRef(true);

  // Lógica de polling de datas e alvos (removendo duplicação do App)
  // ...
  
  const fetchSeries = useCallback((date, target, silent = false) => {
    // Implementação das requisições HTTP REST
  }, [timeframe]);

  const fetchGexForRun = useCallback((runName) => {
    // Requisição incremental de GEX para execuções específicas
  }, [selectedTarget, selectedDate]);

  return {
    dates,
    targetsMeta,
    series,
    summary,
    lastUpdate,
    loading,
    error,
    gexWalls,
    availableRuns,
    selectedRun,
    garchData,
    seriesInfo,
    fetchGexForRun,
    refetchSeries: () => fetchSeries(selectedDate, selectedTarget, true)
  };
}
```

### 3. Canvas Wrapper: `src/components/BaseLightweightChart.jsx`
```javascript
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

    const mergedOptions = {
      ...BASE_CHART_OPTIONS,
      ...chartOptions,
      layout: { ...BASE_CHART_OPTIONS.layout, ...chartOptions.layout },
      crosshair: { ...BASE_CHART_OPTIONS.crosshair, ...chartOptions.crosshair },
      timeScale: { ...BASE_CHART_OPTIONS.timeScale, ...chartOptions.timeScale, visible: !hideXAxis },
      rightPriceScale: { ...BASE_CHART_OPTIONS.rightPriceScale, ...chartOptions.rightPriceScale },
      leftPriceScale: { ...BASE_CHART_OPTIONS.leftPriceScale, ...chartOptions.leftPriceScale },
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
  }, []);

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.timeScale().applyOptions({ visible: !hideXAxis });
    }
  }, [hideXAxis]);

  return (
    <div style={{ background: "#0c1218", borderRadius: hideXAxis ? "0" : "0 0 8px 8px", paddingBottom: 4, position: "relative" }}>
      <div ref={containerRef} style={{ width: "100%", height }} />
      {children}
    </div>
  );
});

BaseLightweightChart.displayName = "BaseLightweightChart";
export default BaseLightweightChart;
```
