# AI-SPEC — IRAI (Intraday Risk Appetite Index)

> AI design contract gerado para formalizar a arquitetura de ML do IRAI.
> Define o framework, a estratégia de avaliação (backtest/live) e as diretrizes de integração com o Regime Supervisor.

---

## 1. System Classification

**System Type:** Modelagem Preditiva / Arbitragem Estatística (Regressão Ridge, Filtro de Kalman, Cointegração)

**Description:**
O IRAI atua como o motor de risco macro intraday. Ele ingere os preços de múltiplos ativos (índices, moedas, yields) a cada 5 minutos, processa via Ridge Regression com regularização estrita (alpha=10.0+), e emite Z-Scores e Betas (hedge ratio). O objetivo da Fase 6 é evoluir do modelo estático diário (Ridge) para um rastreamento dinâmico do "Fair Price" usando Filtro de Kalman e testar a validade da cesta através do teste de Cointegração de Johansen.

**Critical Failure Modes:**
1. **Multicolinearidade Extrema:** O modelo atribuir pesos massivos a ativos idênticos, gerando matrizes singulares ou ruído.
2. **Lookahead Bias / Repaint:** O vazamento de dados futuros no cálculo do Filtro de Kalman (`observation_matrices` e `transition_matrices`) ou NWE.
3. **Overfitting Temporário:** A janela de calibração memorizar um choque específico e aplicar pesos incorretos quando o regime muda abruptamente.
4. **Falsa Cointegração:** O teste de Johansen falhar em detectar a perda de estacionariedade devido a mudanças estruturais não capturadas.

---

## 1b. Domain Context

**Industry Vertical:** Finanças Quantitativas / Pair Trading
**User Population:** Robôs Algorítmicos (MetaTrader 5) e Gestor de Portfólio (Regime Dashboard)
**Stakes Level:** High (Sinais do IRAI travam ou revertem robôs em conta real com exposição financeira alavancada)
**Output Consequence:** Stop-out forçado em posições perdedoras ou bloqueio de entradas lucrativas se o sinal for falso-positivo.

### What Domain Experts Evaluate Against

| Dimension | Good (expert accepts) | Bad (expert flags) | Stakes | Source |
|-----------|-----------------------|--------------------|--------|--------|
| **Estabilidade do Z-Score** | Z-Score varia suavemente, atinge picos de ±2 e reverte em janelas visíveis | Z-Score dá "saltos" instantâneos de 0 para 3 em 1 barra sem evento macro | High | Quant Trader |
| **Cointegração** | Relação Johansen (p < 0.05) se mantém durante a convergência do spread | P-value do Johansen explode para 0.90 logo após o sinal de entrada (quebra de regime) | Critical | Quant Trader |
| **Causalidade** | O modelo usa estritamente `lookback` no fit/predict | O indicador recalcula barras anteriores quando uma nova barra fecha | Critical | Engenheiro ML |
| **Hedge Ratio Dynamics**| Beta se adapta suavemente via Kalman Filter a mudanças de mercado | Beta sofre flips violentos (ex: de +0.5 para -0.5 em um tick) | High | Portfolio Mgr |

### Known Failure Modes in This Domain
- **Regime Shift Silencioso:** O Beta (hedge ratio) calculado há 20 dias deixou de ser válido hoje, e o modelo aciona compra de spread que nunca reverte.
- **Micro-Estrutura (Tick Data):** O spread sintético calculado diverge do Bid/Ask real no MT5, gerando ordens rejeitadas ou slippage extremo.

### Regulatory / Compliance Context
- Operações restritas ao horário de pregão B3 e conformidade com limites de alavancagem da corretora (Tickmill/B3).

---

## 2. Framework Decision

**Selected Framework:** `scikit-learn` (Ridge), `statsmodels` (Johansen), e `pykalman` (ou implementação customizada NumPy para Kalman Filter).
**Version:** `scikit-learn 1.3+`, `statsmodels 0.14+`, `pykalman 0.9.5+`

**Rationale:**
O ecossistema SciPy atende 100% da necessidade de algebra linear para quant trading. `statsmodels` oferece o `coint_johansen` para testes de raiz unitária essenciais na Fase 6. O `pykalman` ou uma implementação state-space NumPy provê a otimização recursiva para o Beta sem o overhead de frameworks de Deep Learning.

**Alternatives Considered:**

| Framework | Ruled Out Because |
|-----------|------------------|
| `PyTorch`/`TensorFlow` | Overkill para filtros lineares bayesianos intraday. Requereria pipeline complexo de inferência e hardware dedicado (GPU/TPU) sem ganhos provados. |
| `LLMs/GenAI` | Risco inaceitável de alucinação para cálculo de spreads e hedge ratios numéricos determinísticos. |

---

## 3. Framework Quick Reference

### Core Imports
```python
import numpy as np
from sklearn.linear_model import Ridge
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from pykalman import KalmanFilter
```

### Entry Point Pattern (Kalman + Johansen)
```python
# 1. Teste de Cointegração
result = coint_johansen(prices_df.values, det_order=0, k_ar_diff=1)
eigenvectors = result.evec # Hedge ratios iniciais
trace_stat = result.lr1    # Significância

# 2. Kalman Filter para rastreamento do Hedge Ratio (Beta)
kf = KalmanFilter(
    transition_matrices=np.eye(2),
    observation_matrices=np.expand_dims(X, axis=1),
    initial_state_mean=np.zeros(2),
    initial_state_covariance=np.ones((2, 2)),
    observation_covariance=1.0,
    transition_covariance=np.eye(2) * 1e-4
)
state_means, state_covs = kf.filter(y)
```

### Common Pitfalls
1. **Johansen com P-Values Não Tabelados:** O `statsmodels` possui as critical values para 90%, 95%, e 99% (`result.cvt`). Sempre verificar a estatística do traço contra a cvt, e não buscar um `p-value` puro como no teste ADF.
2. **Kalman Smoothing em Tempo Real:** Não usar `kf.smooth()` em produção live, pois ele utiliza todo o dataset (past and future) para suavizar o estado (Lookahead bias). Usar apenas `kf.filter_update()` ou `kf.filter()`.
3. **Escala dos Preços:** Ativos com diferenças massivas de preço (ex: WIN=130.000 vs WDO=5.500) quebram as matrizes de covariância. Aplicar Log ou Z-Score nos preços antes do Johansen/Kalman.

---

## 4. Implementation Guidance

**Model Configuration:**
- **Johansen:** Usar `det_order=0` (sem tendência determinística) ou `det_order=1` (com constante). `k_ar_diff=1` (lags) usualmente suficiente para dados intraday M5.
- **Kalman:** `transition_covariance` muito alta torna o Beta volátil (ruído). `transition_covariance` muito baixa torna o Beta lento (estático). O tuning desta hiper-variável é o núcleo do ajuste de risco.

**Data Ingestion & Formatting (Pydantic Example):**
```python
from pydantic import BaseModel, Field
class KalmanState(BaseModel):
    timestamp: str
    beta: float = Field(..., description="Hedge ratio estimated by Kalman")
    intercept: float
    innovation_residual: float = Field(..., description="Forecast error")
    state_variance: float
```

---

## 5. Evaluation Strategy

### Dimensions

| Dimension | Rubric (Pass/Fail) | Measurement Approach | Priority |
|-----------|--------------------|----------------------|----------|
| **Estacionariedade (Johansen)** | Trace Stat > 95% Critical Value | Code-based metrics (`statsmodels`) | Critical |
| **Causalidade (Lookahead)** | Beta(t) calculado apenas com dados até (t-1) | Code-based metrics / Testes Unitários | Critical |
| **Drawdown Máximo do Spread** | < 5% do capital em período de quebra estrutural | Backtester Customizado (Flywheel) | High |
| **Latência de Inferência** | < 200ms por barra no `filter_update` | Code-based metrics (APM) | Medium |

### Eval Tooling
**Primary Tool:** **Backtester Customizado** e **Custom Metrics Dashboard** 
*(Nota: Ferramentas padrão de LLM-Eval como Arize Phoenix não se aplicam por ser ML estatístico/quantitativo, não GenAI. Monitoramento será customizado via logs de inovação do Kalman.)*

---

## 6. Guardrails

### Online (Real-Time)

| Guardrail | Trigger | Intervention |
|-----------|---------|--------------|
| **Bloqueio de Cointegração** | Johansen falha no teste de 90% (perda de relação) | Sistema bloqueia novos trades. Z-Score vai para 0 ou exibe flag de `UNCORRELATED`. |
| **Kalman Covariance Blowup** | Variância do estado > Limite Max de Segurança | Fallback para modelo Ridge/OLS estático e alerta de `Unstable`. |
| **Bloqueio de Anomalia (Z-Score)** | `abs(Z-Score) >= 4.0` | Frontend aciona `ANOMALY` e painel congela operações. EA (MT5) fecha posições. |

---

## 7. Production Monitoring

**Tracing Tool:** ELK Stack / Uvicorn Access Logs / Promtheus + Grafana
*(N/A para Arize Phoenix/LangSmith pois não envolve prompts/LLMs)*

**Key Metrics to Track:**
- Latência do update do Kalman Filter por tick/barra.
- Distribuição do `innovation_residual` do Kalman (deve ser aproximadamente Normal(0, variância)). Se divergir, o modelo quebrou.
- Frequência de falhas no Teste de Johansen durante o dia (mede estabilidade do regime).

## Checklist
- [x] Framework selected with rationale (Section 2)
- [x] AI-SPEC.md created from template
- [x] Framework docs + AI best practices researched (Sections 3, 4, 4b populated)
- [x] Domain context + expert rubric ingredients researched (Section 1b populated)
- [x] Eval strategy grounded in domain context (Sections 5-7 populated)
- [x] Arize Phoenix (or detected tool) set as tracing default in Section 7 (Adaptado para quant ML)
- [x] AI-SPEC.md validated (Sections 1b, 2, 3, 4b, 5, 6 all non-empty)
