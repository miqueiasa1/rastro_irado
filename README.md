# IRAI — Intraday Risk Appetite Index

Dashboard cross-asset em tempo real que estima a **probabilidade de o IBOV fechar o dia em alta**, olhando não para o próprio índice, mas para o comportamento dos mercados que historicamente o lideram: EWZ, VIX, DXY e US10Y.

> *"Neste momento do pregão, o resto do mundo está dizendo que o IBOV deveria estar subindo ou caindo?"*

Atualiza a cada 5 minutos. Reseta no open da B3 (10:00 BRT). Opera com dois terminais MetaTrader 5 simultâneos — um nacional para IBOV/WIN, um internacional para os fatores externos.

## Documentação relacionada

- [`PRD.md`](./PRD.md) — visão, objetivos, escopo, métricas de sucesso
- [`SPEC.md`](./SPEC.md) — arquitetura, schema, algoritmo, API contract

---

## Arquitetura em 30 segundos

```
MT5 Brasil  →  worker_br.py    ↘
                                 →  SQLite (irai.db)  →  FastAPI  →  React
MT5 Intl    →  worker_intl.py  ↗
```

- **Dois workers Python independentes.** Cada um conecta num terminal MT5 via `mt5.initialize(path=...)` — a biblioteca só suporta uma conexão por processo, então a solução é ter dois processos.
- **SQLite com WAL mode** como camada de comunicação — workers escrevem, API lê. Zero infra.
- **FastAPI** calcula o IRAI sob demanda, sem estado em memória.
- **React + Vite** faz polling de 30s no endpoint atual.

---

## Pré-requisitos

### Software

- **Windows** (MT5 não roda nativo em Linux/Mac sem Wine).
- **Python 3.11 ou 3.12** (MetaTrader5 package ainda não suporta 3.13 estável).
- **Node.js 18+**.
- **Git**.

### Contas

Duas contas MetaTrader 5 em brokers diferentes:

1. **Broker BR** — qualquer broker nacional que expõe IBOV e WIN com qualidade intraday. Exemplos: XP, Clear, Rico, Genial, Modal. Demo serve pro MVP.
2. **Broker INTL** — broker offshore com cobertura de CFDs/índices globais. Prioridade de cobertura: VIX, DXY, EWZ, US10Y. Testar antes: Pepperstone, IC Markets, FTMO, XM. Demo serve.

> **Dica:** antes de começar, abra as duas contas demo e rode `scripts/list_symbols.py` (ver §Setup) pra confirmar que cada corretora tem os símbolos necessários. Se o broker INTL não tiver `US10Y`, o fallback é usar `TLT` (inverter o sinal do peso no `.env`).

---

## Setup — passo a passo

### 1. Instalar os dois terminais MT5

Baixar o instalador de cada broker e instalar em diretórios distintos:

```
C:\Program Files\MetaTrader 5 BR\
C:\Program Files\MetaTrader 5 INTL\
```

Durante o segundo instalador, **trocar o diretório de destino** — senão sobrescreve o primeiro. Depois, abrir cada terminal uma vez, logar com a conta respectiva, e deixar os símbolos necessários habilitados em Market Watch (Ctrl+M).

### 2. Clonar o projeto e instalar dependências

```bash
git clone <repo> irai
cd irai

# Backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

### 3. Configurar `.env`

Copiar `.env.example` pra `.env` e preencher:

```ini
# ─── MT5 Brasil ─────────────────────────────────
MT5_BR_PATH="C:\Program Files\MetaTrader 5 BR\terminal64.exe"
MT5_BR_LOGIN=12345678
MT5_BR_PASSWORD=<sua_senha>
MT5_BR_SERVER=XPMT5-DEMO
MT5_BR_SERVER_OFFSET_HOURS=-3

# Símbolos BR (ajustar ao nome usado pelo seu broker)
SYMBOL_IBOV_BR=IBOV
SYMBOL_WIN_BR=WIN$N

# ─── MT5 Internacional ──────────────────────────
MT5_INTL_PATH="C:\Program Files\MetaTrader 5 INTL\terminal64.exe"
MT5_INTL_LOGIN=87654321
MT5_INTL_PASSWORD=<sua_senha>
MT5_INTL_SERVER=Pepperstone-Demo
MT5_INTL_SERVER_OFFSET_HOURS=3

# Símbolos INTL
SYMBOL_VIX_INTL=VIX
SYMBOL_DXY_INTL=DXY
SYMBOL_EWZ_INTL=EWZ
SYMBOL_US10Y_INTL=US10Y
# Se seu broker não tem US10Y nativo, descomente e use TLT:
# SYMBOL_US10Y_INTL=TLT
# WEIGHT_US10Y_SIGN_FLIP=true

# ─── App ────────────────────────────────────────
DB_PATH=./data/irai.db
API_PORT=8000
LOG_LEVEL=INFO
```

### 4. Descobrir os símbolos disponíveis em cada broker

```bash
python scripts/list_symbols.py --source br
python scripts/list_symbols.py --source intl
```

Cada chamada conecta no MT5 respectivo e lista todos os símbolos que contêm keywords relevantes (VIX, DXY, EWZ, IBOV, US10, etc.) com status de cotação. Ajustar os nomes no `.env` conforme o retorno.

### 5. Validar offsets de server time

```bash
python scripts/validate_offsets.py
```

Compara o `time` de uma tick ao vivo com `datetime.utcnow()` e reporta o offset real. Ajustar `MT5_*_SERVER_OFFSET_HOURS` se necessário.

### 6. Inicializar o banco e popular parâmetros seed

```bash
python -m backend.db init
python scripts/seed_params.py
```

Cria `data/irai.db` com schema e insere pesos/α/σ iniciais (valores default do SPEC §15.1). Depois do primeiro ciclo de calibração, esses valores são substituídos por estimativas empíricas.

---

## Como rodar

Três processos em paralelo, cada um em seu terminal:

```bash
# Terminal 1 — worker Brasil
python -m backend.workers.worker_br

# Terminal 2 — worker internacional
python -m backend.workers.worker_intl

# Terminal 3 — API
uvicorn backend.api.main:app --reload --port 8000

# Terminal 4 — frontend
cd frontend && npm run dev
```

Dashboard em `http://localhost:5173`. API em `http://localhost:8000/docs` (Swagger).

### Atalho Makefile

```bash
make start-workers   # sobe os 2 workers em background
make start-api       # sobe FastAPI
make start-frontend  # sobe Vite
make logs            # tail -f nos 4 logs
make stop            # mata todos os processos
```

---

## Calibração

Rodar semanalmente (sábado ou domingo):

```bash
python -m backend.calibrate --window-days 60
```

Isso:
1. Lê histórico diário dos 5 símbolos do banco.
2. Estima pesos via regressão linear multivariada.
3. Estima σ_i via desvio-padrão anualizado.
4. Estima α via regressão logística em série intraday.
5. Grava novos parâmetros em `model_params` com `effective_from = hoje`.
6. Gera `data/reports/calibration_YYYYMMDD.md` com diagnóstico.

**Sempre revisar o relatório antes de aceitar a nova calibração** — se algum peso inverteu sinal, é sintoma de regime shift ou problema nos dados.

---

## Estrutura do projeto

```
irai/
├── backend/
│   ├── workers/        ← worker_br.py, worker_intl.py
│   ├── api/            ← FastAPI
│   ├── irai/           ← lógica de cálculo
│   └── calibrate.py
├── frontend/           ← React + Vite
├── data/
│   ├── irai.db         ← SQLite (gitignored)
│   └── reports/        ← relatórios de calibração
└── scripts/            ← utilitários de setup e manutenção
```

Detalhamento completo em [`SPEC.md §11`](./SPEC.md).

---

## Troubleshooting

### `mt5.initialize()` retorna False

- Confirmar que o terminal está aberto E logado antes de subir o worker.
- Rodar o worker como Administrador (algumas instalações exigem).
- Verificar que o `path` no `.env` aponta exatamente pro `terminal64.exe`, não pra pasta.
- Checar `mt5.last_error()` nos logs pra código específico.

### Só um worker funciona; o segundo falha silenciosamente

Sintoma clássico de tentar rodar duas conexões no mesmo processo Python. Confirmar que `worker_br.py` e `worker_intl.py` são **processos separados** (dois terminais, dois `python -m ...`).

### Símbolo não encontrado no Market Watch

- Abrir o terminal manualmente, Ctrl+M, buscar o símbolo e habilitar.
- Alguns brokers só expõem certos símbolos pra contas específicas — contactar suporte.

### Timestamps estão saindo errados (barras no futuro ou no passado)

- Rodar `python scripts/validate_offsets.py` e ajustar `*_SERVER_OFFSET_HOURS` no `.env`.
- Verificar se o broker mudou o server recentemente (DST).

### Dashboard mostra P_up = 50% fixo

- API provavelmente não achou `session_opens` — rodar `python -m backend.irai.session backfill --date today`.
- Ou `model_params` está vazio — rodar `python scripts/seed_params.py`.

### VIX marcado como `stale` nos primeiros 30 min do pregão

Comportamento esperado. O CBOE abre às 9:30 ET = 10:30 BRT. Nos primeiros 30 min da sessão B3, o VIX usa o close do dia anterior. Normal, não é bug.

### `copy_rates_from_pos` retorna None

- Símbolo não está habilitado em Market Watch.
- Mercado fechado (ex: tentar puxar VIX às 03:00 BRT).
- Conexão do terminal caiu (olhar canto inferior direito do MT5).

---

## Roadmap

### MVP (atual)

- [x] Protótipo visual (React)
- [ ] Workers MT5 duplos
- [ ] FastAPI + SQLite
- [ ] Script de calibração
- [ ] Integração frontend ↔ backend
- [ ] 5 pregões de validação ao vivo

### V2

- [ ] WebSocket push em vez de polling
- [ ] Alertas desktop / som ao cruzar thresholds
- [ ] Navegação por sessões históricas no dashboard
- [ ] Métricas de calibração expostas no próprio dashboard
- [ ] Alvos adicionais além do IBOV (WIN isolado, small caps, BRL)

### V3

- [ ] Integração com supervisor SQX dos 55 robôs
- [ ] Ajuste automático de exposição em função do regime
- [ ] Dashboard mobile (PWA)

---

## Licença & notas

Projeto pessoal, uso interno. Não é um produto financeiro regulado. **IRAI é uma ferramenta de suporte à decisão, não uma recomendação de investimento.** Sinais do modelo não substituem análise de risco própria.

---

**Autor:** Miqueias
**Início:** 2026-04-23
