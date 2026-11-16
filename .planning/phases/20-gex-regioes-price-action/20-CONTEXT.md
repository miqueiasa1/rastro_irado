# Phase 20 Context: Regiões de GEX + Gatilho de Price Action, com o Rastro como Contexto

**Data:** 2026-11-10 · **Status:** planejamento (nada implementado, nada commitado)
**Branch local:** `v2/fase-20-gex-pa` (criada de `751fb43` no worktree `rastro_irado_wt_f17_18`)
**Princípio do owner:** "o rastro dá o contexto, o GEX dá a região e o price action dá o gatilho."
**Escopo fixo:** só WIN$N e WDO$N · horizonte 60 min · custos 10 pts (WIN) e 1 pt (WDO) por operação ida e volta · apoio à decisão, nunca execução automática.

Todos os números abaixo foram medidos em 10/11/2026 (~18:30 BRT), lendo `data\irai_live.db` em **modo somente leitura** (`file:...?mode=ro`) e os arquivos do projeto WDO (`..\wdo win pair trading\gex\data\`). Scripts de medição: `%TEMP%\irai_p20\inv1.py` a `inv10.py` (descartáveis, fora do repositório). Sessões em horário de Brasília, barras M5 das 09:00 às 18:25, convertidas com `backend.eval.data.broker_wall_to_brt` (o `timestamp_utc` do banco é o relógio do broker, NY+7).

---

## 1. Por que a fase 20 muda de forma

A fase 20 original (PHASES.md) testava GEX e fluxo como **features do p_fwd_60** (ΔBSS). A fase 18 mostrou que o p_fwd_60 não tem sinal (AUC 0,48–0,50, BSS ≤ 0) e que o valor justo da cesta tem z bem escalado mas sem poder preditivo (AUC ~0,5). Por isso, esta fase troca a pergunta:

> Um alerta **evento** (preço chega a uma região de GEX conhecida antes da abertura → gatilho de price action → direção confirmada pelo rastro) tem P&L líquido de custos positivo e estável fora da amostra?

O rastro entra como **filtro de direção/contexto**, não como gatilho. A fase 18 deixou só sinais fracos: reversão pequena no WDO (`cesta_w60_movel40`, +0,4 a +0,6 pt bruto a 15 min, abaixo do custo) e WIN com sinal trocado entre desenho e validação (−88 pts / +232 pts).

---

## 2. Inventário do GEX

### 2.1 Origem e fluxo
- O projeto WDO calcula os níveis (`gex/engine/main.py`, `main_dol.py`, `walls_calculator.py`, `b3_history_calculator.py`) a partir das planilhas de **posições em aberto da B3** e gera `gex/docs/jumba_tradingview.pine`.
- `scripts/sync_gex_to_irai.py` (chamado pelo `GEX_DAILY_ALL.bat`) lê o Pine e:
  1. reescreve `frontend/src/gexLevels.js` (só o dia corrente; 15 ativos; último: 10/11/2026 07:32, 34 níveis no WIN e 34 no WDO);
  2. grava `gex_levels(session_date, target, run_name, levels_json, updated_at)` com `INSERT OR REPLACE`; `session_date` = data local do PC na hora do run; `run_name` = HH:MM local; `updated_at` = `datetime('now')` do SQLite (**UTC real**);
  3. publica no RTDB (`summaries/gex/...`, `gex_pine`, `pine_vault`).
- `scripts/backfill_gex_history.py` reconstrói runs a partir do **histórico git** do projeto WDO; `updated_at` = hora do commit (convertida para UTC), não a hora de publicação.

### 2.2 Tipos de nível (o que existe de fato)
`wall` (MAGICWALL, força 1–3 estrelas = `width`), `mid_wall` (ponto médio entre walls), `min_gamma` (piso), `max_gamma` (teto), `gamma_flip` (pivô). **Não existem** "call wall" e "put wall" separados.
- No WIN, cada wall é um strike de IBOV convertido para o futuro (ex.: "MAGICWALL * (IBOV 161000)" → 162.668,55). Espaçamento wall/mid_wall: mediana **507 pts** (p10 507, p90 1.014). É uma grade de strikes; a informação está na força (`width`) e em min/max/flip.
- No WDO, walls em strikes do DOL; espaçamento mediano **15 pts** (p10 10, p90 25).
- Por run: 34 níveis (mín. 22 no WIN e 6 no WDO). Walls fortes (`width ≥ 2`): mediana **3 por sessão** nos dois ativos.
- O arquivo diário `jumba_gex_wdo_daily.json` traz o GEX por strike (`gex`), útil para pesar zonas; o histórico no banco guarda só preço/rótulo/largura.

### 2.3 Cobertura no banco (`gex_levels`)
| Ativo | Linhas | Sessões | Primeira | Última | Runs distintos | Sessões com run antes de 09:00 BRT (same day) |
|---|---|---|---|---|---|---|
| WIN$N | 250 | 132 | 11/05/2026 | 10/11/2026 | 100 | **118** (114 + 4 com run de outra data também) |
| WDO$N | 242 | 125 | 23/05/2026 | 10/11/2026 | 94 | **116** (112 + 4) |

- Runs por sessão (WIN): 1 run em 45, 2 em 70, 3 em 9, 4 em 6, 6 em 1, 8 em 1. WDO: 39 / 69 / 9 / 6 / 1 / 1.
- Hora do `updated_at` (UTC; 12:00 UTC = 09:00 BRT): 115 runs (WIN) às 10h UTC (~07:30 BRT, o horário normal recente); 16 às 11h; 14 às 12h; **69 às 21h UTC (~18h BRT, depois do fechamento)**; 13 com data UTC do dia seguinte (00–02h UTC, ver 23/05).
- Sessões **sem** run antes de 09:00: WIN 14, WDO 9. Ex.: as primeiras sessões do WIN (11/05 a 19/05) têm run às 09:13–09:53 BRT, depois da abertura.
- 23/05/2026 (sábado) tem 6 runs das 19:34 às 22:51 BRT — padrão de backfill/teste, não de publicação.
- Dias com GEX e sem barras de pregão: 23/05, 07/09, 12/10, 01/11, 02/11.
- **Sessões elegíveis (run as-of antes de 09:00 + barras do pregão): WIN 115, WDO 113.** Por mês (WIN): mai 6, jun 21, jul 23, ago 20, set 18, out 21, nov 6. Até 31/08: WIN 70, WDO 68; set–nov: 45 e 45.

### 2.4 Lookahead visual no gráfico de dias passados (achado)
`GET /api/gex` sem `run` escolhe `ORDER BY run_name DESC` → o **último** run do dia. Em **75 sessões** (WIN e WDO), esse run padrão não é o run as-of; em 68 (WIN) e 69 (WDO) os níveis são diferentes. No WIN, o `gamma_flip` muda em mediana **1.016 pts** (máx. 21.987); no WDO a mediana é 0 (máx. 27,45). Ou seja, os gráficos de dias passados podem mostrar níveis publicados **depois** do pregão. Isso não afeta o cálculo do P (o GEX não entra no modelo), mas afeta qualquer leitura visual de "o preço respeitou a wall" e precisa ser corrigido antes de alertas.

### 2.5 Histórico mais longo no projeto WDO (fora do banco)
- `gex/data/b3_gex_history_2026.csv`: **212 sessões** (02/01 a 06/11/2026), por mês 21/18/22/20/20/22/22/21/21/21/4. Colunas: `s_ibov`, `f_win`, `win_flip`, `win_max_gamma`, `win_min_gamma`, `wdo_close`, `dol_flip`, `dol_max_gamma`, `dol_min_gamma`, contagem de opções. **Só flip/min/max, sem walls.**
  - `source`: `BACKFILLED_B3` 86 (jan–mai), `PRESERVED_HEAD` 126 (mai–nov, contagem de opções −1).
  - `ref_oi_date` = pregão anterior em 165 linhas, 2–5 dias antes em 46 (fins de semana/feriados), igual à data em 1 (02/01). Por construção, usa posição em aberto de D−1 — **causal se a planilha de D−1 está disponível antes de 09:00 de D** (os arquivos diários recentes têm mtime ~07:30 do dia seguinte; os de jan–abr foram baixados em lote em 08/11/2026).
  - Flip do CSV × flip do banco (run as-of) nas sessões em comum: diferença mediana 0,002 pt (WIN, n=112) e 0 (WDO, n=110) — o trecho `PRESERVED_HEAD` é o mesmo dado do banco.
- 214 planilhas `Posições em aberto-DD-MM-AAAA.csv` (02/01 a 09/11/2026) e `chain_archive/` (193 arquivos, desde 28/10): matéria-prima para **recalcular walls de forma causal** desde janeiro, com o código do projeto WDO.
- `jumba_gex_win_history.json` / `jumba_gex_wdo_history.json`: 119 sessões cada (07/05–23/10), com walls; gerados em 25/10 (reconstrução, não publicação ao vivo).

### 2.6 Q5 (em aberto)
"O projeto WDO garante GEX publicado antes de 09:00 e marca o backfill?" Medido: o banco **não** tem marca de backfill (só dá para inferir pelo `updated_at`); o CSV tem `source`. Proposta desta fase: `gex_asof_ok=1` só com run de `updated_at` < 12:00 UTC na própria data e não oriundo de backfill; `gex_asof_ok=2` para níveis reconstruídos de D−1 (análise separada, nunca misturada com a principal). Continua pendente de confirmação do projeto WDO.

---

## 3. Inventário de preço (WIN$N, WDO$N, fonte `br`)

| Timeframe | WIN$N | WDO$N |
|---|---|---|
| M5 | 115.547 barras, 16/09/2022 → 10/11/2026 (1.142 datas) | 115.536, 28/09/2022 → 10/11/2026 (1.134) |
| M1 | 53.264, desde 29/05/2026 (cheio a partir de jul: ~25–27 pregões/mês) | 54.243, desde 05/06/2026 (cheio a partir de jul) |
| M2/M15/M30/H1 | desde mai–jun/2026 | idem |
| D1 | 450 barras, 05/07/2024 → 24/04/2026 (parado) | idem |

- Pregões M5 em 2026 (09:00–18:25 BRT): 214 por ativo; um dia típico tem 113 barras (09:00–18:20).
- `delta` M5 ≠ 0: WIN em ~98% das barras desde jan/2026; **WDO só desde abr/2026** (0 em jan–mar, 402 de 2.279 em abr, ~90% de mai em diante).
- Volatilidade 2026 (por pregão): range diário mediano **WIN 3.030 pts** (p25 2.461, p75 4.043) e **WDO 45 pts** (35,6 / 60,9). TR M5 mediano 225 / 3,5; **ATR14 (M5, causal) mediano 258 / 4,14**.
- Movimento de 60 min (mai–nov): |mov| mediano **WIN 320 pts, WDO 5 pts**; desvio-padrão 709 e 10,7 (caudas pesadas). Custo/ATR: WIN 3,9%, WDO 24%. |mov 60 min| ≤ custo em 2,2% (WIN) e 13,3% (WDO) das barras.
- Gaps de abertura > 2% (possível rolagem/erro de série, a tratar): WIN 29/07, 05/10, 26/10; WDO 05/10, 26/10.
- Snapshots ao vivo (`irai_live_snapshots`, contexto do rastro gravado): WIN 98 sessões (02/08–10/11), WDO 87 (03/08–10/11). O valor justo da cesta (fase 18) é recalculável de forma causal a partir de `market_bars` para todo o período do GEX.

---

## 4. Seletividade das zonas (medida, sessões as-of)

Zona = nível ± k·ATR14(M5) da barra anterior. Fração das barras do pregão dentro de alguma zona (mediana por sessão):

| Conjunto de níveis | WIN k=0,5 | WIN k=1 | WDO k=0,5 | WDO k=1 | Distância mediana preço→nível |
|---|---|---|---|---|---|
| Todos (grade wall+mid) | 48,7% | 76,1% | 30,1% | 54,0% | 140 pts / 3,5 pts |
| Walls fortes (width ≥ 2) | 0% | 0% | 0% | 0% | 2.084 pts / 33,5 pts |
| min/max/flip | 0% | 0% | 0% | 0% | 4.015 pts / 65,2 pts |

Eventos (entrada na zona k=0,5 após ≥ 3 barras fora), 115 sessões WIN / 113 WDO:

| Conjunto | WIN: sessões tocadas | WIN: entradas/pregão | WDO: sessões tocadas | WDO: entradas/pregão |
|---|---|---|---|---|
| Todas as walls | 114 (99%) | 4,41 (507) | 107 (95%) | 3,74 (423) |
| Walls fortes (≥ 2) | 47 (41%) | 1,30 (149) | 44 (39%) | 1,25 (141) |
| Walls 3 estrelas | 36 (31%) | 0,87 (100) | 17 (15%) | 0,36 (41) |
| min/max/flip | 26 (23%) | 0,59 (68) | 24 (21%) | 0,45 (51) |

CSV jan–nov (211 sessões com barras): flip tocado em 23 (11%) no WIN e 42 (20%) no WDO; min_gamma 15 (7%) / 11 (5%); max_gamma WIN 12 (6%).

Regime de gama: o preço fica entre min_gamma e max_gamma em 100% das barras (mediana). Em relação ao flip, a sessão costuma ficar inteira de um lado: WIN 67 sessões 100% acima, 37 100% abaixo, 11 mistas; WDO 48 / 44 / 21. O lado do flip serve como rótulo de regime **por sessão**, não como nível tocado.

**Conclusões do inventário**
1. A grade completa de walls não é seletiva (o preço está "numa zona" metade do tempo). A região útil são as walls fortes e, mais raramente, min/max/flip.
2. Histórico as-of: **115 (WIN) / 113 (WDO) sessões**, ~1,3 evento por pregão nas walls fortes → ~150 eventos antes dos gatilhos.
3. Poder estatístico (derivado das medidas acima; MDE 80% ≈ 2,8·σ/√n): com σ = 709 pts (WIN), MDE por operação 281 / 198 / 162 pts para n = 50 / 100 / 150; com σ robusto (1,4826 × 320 = 474 pts), ~108 pts em n = 150. WDO: 4,3 / 3,0 / 2,5 pts (σ = 10,7); ~1,7 pt com σ robusto. **O histórico basta para detectar só efeitos grandes; um resultado "inconclusivo" é o mais provável.** Ampliar o histórico (walls recalculados de D−1 desde jan) e acumular shadow ao vivo são as alavancas.
4. O REQ-G04 pede ≥ 40 pregões elegíveis: atendido no total (115/113) e em cada metade (70/45 WIN; 68/45 WDO).
---

## 5. Atualização de 10/11/2026 (noite): fonte oficial do histórico de GEX

Decisão do owner: o histórico oficial é o CSV do projeto WDO em `mt5/Files/` (lido sem alterar):

| Arquivo | Sessões | Período | Weekend no arquivo | Níveis/sessão (mediana) | N1/sessão (mediana; mín.) |
|---|---|---|---|---|---|
| `jumba_gex_win_history.csv` | 221 | 02/01–10/11/2026 | 23/05, 29/08, 01/11 | 34 | 6; 5 |
| `jumba_gex_wdo_history.csv` | 217 | 02/01–10/11/2026 | 01/11 | 34 | 6; 5 |

- Formato `session_date;type;price;width`, tipos `Wall/MidWall/MaxGamma/MinGamma/GammaFlip`, width 1–3.
- Jan–mai (calculados com a posição em aberto do pregão anterior) são **oficiais** e entram na amostra principal como conhecidos na abertura; não há camada separada.
- Q5, regra adotada: sem marca de backfill; onde o CSV não tem a data, usa-se o **primeiro** run com `run_name` < 09:00 em `gex_levels`; sem run → sessão fora. Na prática o fallback não foi usado (WIN 0, WDO 0; as datas do WDO sem CSV, 07/09 e 12/10, são feriados).
- CSV × banco nas datas em comum: flip com diferença mediana 0,002 pt (WIN) e 0 (WDO); conjunto N1 idêntico em 95 de 118 (WIN) e 104 de 114 (WDO) sessões.
- Com isso, todas as 213 sessões com barras de 2026 têm GEX; depois das exclusões por gap de abertura > 2%, ficam **208 (WIN) e 211 (WDO)** sessões, contra 115/113 do inventário anterior. Resultados em `20-SUMMARY-01.md`.