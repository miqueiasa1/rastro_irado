# IRAI — Intraday Risk Appetite Index (V2 Multi-Asset)

Dashboard cross-asset em tempo real que estima a **probabilidade direcional intraday (alta/baixa)** de 20 ativos globais (Indices, Moedas, Commodities e Crypto), inferida a partir de uma regressao multipla (Ridge) sobre **27 fatores candidatos** (21 tradicionais + 6 iShares Axi ETFs).

> *"Neste momento do pregão, o resto do mundo está dizendo que este ativo deveria estar subindo ou caindo?"*

Atualiza a cada 60 segundos. Reseta no open da Sessao. Opera com **tres terminais MetaTrader 5** em paralelo -- um nacional (XP) para WIN/DOL/DI (09h-18h), um internacional (Tickmill) para todo o resto (24h), e um terceiro (Axi) para 6 iShares ETFs usados como fatores de calibracao (16h-23h UTC).

## Documentação relacionada

- [`PRD.md`](docs/PRD.md) — visão, objetivos, escopo, métricas de sucesso
- [`SPEC.md`](docs/SPEC.md) — arquitetura, schema, algoritmo, API contract

---

## Performance do Modelo (V2 - Ridge Regularization)

O novo motor Multi-Asset V2 calibra 20 ativos dinamicamente garantindo que não haja *overfitting* via Filtros de Correlação Cruzada e Penalidade L2 (Ridge).

**Cobertura de Acuracia Direcional (pos-calibracao 2026-04-28, com iShares Axi):**
- **Moedas/Forex Major:** 82% a 90% (EURUSD 89.9%, AUDUSD 89.9%, USDCHF 88.4%, GBPUSD 86.5%, USDCAD 84.1%, USDJPY 81.6%)
- **Indices Americanos:** 80% a 87% (US500 87.4%, USTEC 84.1%, US30 80.2%)
- **Mercado BR:** 84% (WIN$N 84.5%, WDO$N 83.5%)
- **Cross Pairs:** CADCHF 84.5%, AUDNZD 81.2%, EURGBP, EURCHF, EURJPY, GBPJPY, EURAUD
- **Crypto e Metais:** 73-76% (BTCUSD 75.8%, XAUUSD 72.5%)

> 12 de 20 modelos selecionaram pelo menos 1 fator iShares. Todos os 6 ETFs entraram em >= 2 modelos.

Para a tabela completa de fatores de cada ativo, seus pesos normalizados ($w_i$), sigmas ($\sigma$) e acurácias individuais, consulte o documento dinâmico [`FACTOR_MAP.md`](docs/FACTOR_MAP.md).

---

## Arquitetura em 30 segundos (Cloud Híbrida)

```
MT5 Brasil (XP)     -+                                  +-> Firebase Realtime DB
                      |                                  |
MT5 Tickmill        --+-> collector.py -> API :8888 ----+-> firebase_sync.py
                      |                          |               |
MT5 Axi (iShares)  -+                        SQLite             v
                                                         React Frontend (Firebase)
```

- **Collector unificado:** coleta sequencial dos 3 terminais MT5 a cada ciclo (60s). Axi coleta 6 iShares ETFs (fatores de calibracao apenas).
- **SQLite (WAL):** armazena o histórico cru e metadados.
- **FastAPI:** expõe endpoints com cálculos sob demanda (IRAI + Fatores) + **cache server-side** por `(target, date)` invalidado a cada coleta.
- **Sincronizador (firebase_sync.py):** roda em background (NSSM) empurrando o estado atual pra nuvem a cada 30s.
- **Frontend (Firebase Hosting):** site passivo acessível globalmente via celular/desktop, lendo o JSON hospedado.
- **Atualização local:** HTTP polling a cada 60s (sem WebSocket — estabilidade priorizada sobre latência).

---

## Pré-requisitos

### Software

- **Windows** (MT5 não roda nativo em Linux/Mac).
- **Python 3.11+** com `MetaTrader5`, `numpy`, `pandas`, `scikit-learn`, `scipy`.
- **Node.js 18+**.

### Terminais MT5

1. **XP** -- `C:\Program Files\MetaTrader 5 Terminal\terminal64.exe`
   - Simbolos: `WIN$N`, `DOL$N`, `DI1$N`
2. **Tickmill** -- `C:\Program Files\Tickmill MT5 Terminal\terminal64.exe`
   - Simbolos: `DXY`, `BRENT`, `CHINA50`, `USDMXN` + 19 ativos globais
3. **Axi** -- `C:\Program Files\Axi MetaTrader 5 Terminal\terminal64.exe`
   - Simbolos: `iSharesBrazil+`, `iSharesTreasury20+`, `iSharesTreasury10-20+`, `iSharesTreasury1-3+`, `iSharesUSEmerging+`, `iSharesCurrencyBond+`
   - Apenas fatores de calibracao (nao entram no dashboard)

---

## Como rodar

A infraestrutura foi configurada para rodar **100% invisível em background** usando o **NSSM** no Windows.

### Inicio Rapido (start_irai.bat):
Para iniciar todos os servicos de uma vez:
```cmd
start_irai.bat
```
Isso inicia API (porta 8888), Collector (3 terminais MT5), e Frontend (porta 5175).

### Instalacao dos Servicos (NSSM):
Abra o PowerShell como Administrador e rode:
```powershell
.\scripts\install_nssm_services.ps1
```

Isso instalará 3 serviços automáticos:
1. `IRAI_API` (Uvicorn FastAPI na porta 8888)
2. `IRAI_Collector` (Sincroniza o MT5 pro SQLite a cada 60s)
3. `IRAI_FirebaseSync` (Lê a API local e empurra o payload pro Firebase a cada 30s)

### Frontend (Nuvem):
O React já está empacotado e hospedado publicamente no Firebase Hosting. Para acessar, abra `rastromacro.web.app` em qualquer dispositivo.

Para desenvolvimento local do frontend:
```bash
cd frontend && npm run dev
```

---

## Calibração (Motor V2)

Para recalibrar automaticamente toda a malha de ativos globais, execute:

```bash
python -X utf8 scripts/calibrate_universal.py --all --force
```

Para recalibrar apenas os pares de moedas major (EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF) **sem DXY** (exclusão obrigatória — multicolinearidade):
```bash
python calibrate_majors_nodxy.py
```

Isso dispara o processo completo:
1. Extrai retornos de sessões construídos a partir de blocos exatos M5 para cada ativo.
2. Aplica regras de exclusão: BR isolado de Internacional; índices US não usam DXY; **majors forex não usam DXY** (DXY é derivado dos próprios pares).
3. Executa brute-force em todos os alvos, buscando combinações (entre 4 e 8 fatores) com Score Misto: 70% Acurácia + 30% R².
4. Calibra logistic regression (α, intercept) sobre o score linear para mapear em probabilidade [0–100%].
5. Atualiza os metadados do SQLite (`asset_models` e `model_params`).

Para regenerar a documentação após a calibração:
```bash
python -X utf8 scripts/generate_factor_map.py
```

---

## Estrutura do projeto

```
rastro_irado/
├── backend/
│   ├── workers/
│   │   └── collector.py     ← coleta unificada (BR + Tickmill)
│   ├── api/
│   │   └── main.py          ← FastAPI (porta 8888)
│   ├── irai/
│   │   └── engine.py        ← motor de cálculo IRAI
│   └── db.py                ← conexão SQLite
├── frontend/
│   └── src/App.jsx          ← React dashboard
├── data/
│   ├── irai.db              ← SQLite (gitignored)
│   └── reports/             ← relatórios de calibração
└── scripts/
    └── calibrate_m5.py      ← calibração offline
```

---

## Roadmap

### V1 (atual) ✅

- [x] Collector MT5 sequencial (2 terminais)
- [x] FastAPI + SQLite com WAL
- [x] Engine de cálculo IRAI (z-score + OLS + logística)
- [x] Calibração automatizada com relatório
- [x] Dashboard React com gráficos Recharts
- [x] Velocímetro P(↑) com sinal COMPRA/VENDA/NEUTRO
- [x] Fluxo Delta (book pressure)
- [x] 6 fatores otimizados (brute-force 64 combos → 71% acc)
- [x] Validação ao vivo (operacional desde 2026-04-23)

### V2 (atual) ✅

- [x] Expansão Multi-Asset (20 Alvos simultâneos)
- [x] Brute-force Calibrador V2 (`calibrate_v2.py`)
- [x] Regressão Ridge (Alpha Regularization) para prevenir Overfitting
- [x] Filtros Dinâmicos de Correlação Cross-Asset
- [x] Dashboard dinâmico exibindo Divergência de Preço (Z-Score) e NWE
- [x] Refinamentos UI/UX: Interatividade profunda com Zoom/Pan nos gráficos e iconografia com 2-letter codes.
- [x] **Hierarquia Visual de Alertas**: Adição de micro-badges D-P-Z-E (Divergência, Pullback, Z-Score, Exaustão) locais, reservando o "blink" global da UI apenas para Divergência de Retorno Direcional.
- [x] **UX Simplificada**: Remoção de sparklines da tela de Overview para focar em legibilidade mobile.
- [x] **Arquitetura Cloud Híbrida**: Firebase Realtime DB + Hosting para acesso mobile.
- [x] **Deploy Invisível**: Instalação automatizada via NSSM Services (`install_nssm_services.ps1`).

### V3

- [ ] Integração com Regime Supervisor (ajuste de exposição por regime IRAI em MT5 portfólios)
- [ ] Ensemble com features de microestrutura (book, trades)
- [ ] WebSocket push em vez de polling
- [ ] Alertas desktop / som ao cruzar thresholds

---

## Licença & notas

Projeto pessoal, uso interno. **IRAI é ferramenta de suporte à decisão, não recomendação de investimento.**

**Autor:** Miqueias
**Início:** 2026-04-23
**Ultima atualizacao:** 2026-04-28

## Arquitetura Multi-Ativo (V2 + iShares)
O sistema cobre 20 ativos globais com 27 fatores candidatos (incluindo 6 iShares Axi). Para entender a relacao de fatores e pesos de cada modelo, consulte o [FACTOR_MAP.md](docs/FACTOR_MAP.md).
