# Fase 20b — Pré-registro: fluxo (delta acumulado) como filtro de GEX + price action no WIN$N

**Escrito e commitado ANTES da execução:** 16/11/2026 (BRT). Autorizado pelo owner em 16/11/2026 09:41: um único teste pré-registrado, só WIN$N, só pesquisa (nada vai para produção).
**Código:** `scripts/research_flow_20b.py` (reusa sem alterar `scripts/research_gex_pa.py`, `backend/eval/pa_triggers.py`, `backend/eval/trade_sim.py`, `backend/irai/gex_asof.py`). **Config congelada:** `data/eval/fase20b/config_<hash>.json` (o hash está na mensagem do commit e no relatório; `--run` recusa rodar se o CONFIG mudar).

## 1. Hipótese
No WIN$N, entre os alertas do melhor braço da fase 20 (**C_T3_C1**: zona de GEX as-of + gatilho T3 rompimento/reteste + rastro C1 a favor pelo valor justo da cesta), exigir que o **fluxo do pregão esteja a favor** do lado da operação aumenta o P&L líquido por operação, de forma estável fora da amostra e melhor que os controles. Princípio do owner: rastro = contexto, GEX = região, price action = gatilho; o fluxo entra como segundo contexto.

## 2. Definição do filtro (causal)
- `cdn(t) = Σ delta / Σ |delta|` das barras M5 do pregão desde 09:00 BRT até a barra t (`market_bars.delta`), em [−1, 1].
- No sinal da barra t usa-se `cdn(t−1)` (só informação até a barra anterior, mesma convenção do C1).
- Compra exige `cdn(t−1) > 0`; venda exige `cdn(t−1) < 0`. Sem delta no pregão até t−1 → sem alerta.
- Braço primário: **F_T3_C1** = C_T3_C1 ∧ filtro de fluxo.

## 3. Dados e protocolo (idênticos à fase 20, config `c985f6b2365e`)
- WIN$N, pregões 02/01/2026 a 10/11/2026; desenho ≤ 30/06/2026, validação depois. GEX: CSV oficial do projeto WDO, fallback primeiro run < 09:00; exclusões iguais (23/05, gaps de abertura > 2%).
- Zona = nível N1 ± 0,5·ATR14 (piso 2× custo); gatilhos, simulador (stop 0,1 ATR além do nível, alvo 1,5 R ou nível, 12 barras), custo 10 pts por operação.
- IC 95% por bootstrap de pregões (B = 2000, seed 0).
- Controles: base **C_T3_C1** (sem fluxo) na mesma rodada; **P1** = T3 + C1 + fluxo em mínimos/máximos de 12 barras fora das zonas de GEX; **P2** = 200 grades de GEX deslocadas (25–75% do espaçamento, sinal aleatório, seed 20).
- Família de testes = 1 (só o braço primário decide; sem correção de multiplicidade). Descritivos, sem peso no veredito: F_T2_C1 e F_T3_C0.

## 4. Métrica primária
Média do P&L líquido por operação (pontos de WIN, já descontado o custo de 10 pts) do braço F_T3_C1.

## 5. Critério de decisão (fixado antes)
**GO** se TODOS:
1. IC 95% da média líquida > 0;
2. média > 0 no desenho e na validação, com n ≥ 30 operações em cada metade;
3. incremento do fluxo: IC 95% de (F_T3_C1 − C_T3_C1) > 0;
4. controles: IC 95% de (F_T3_C1 − P1) > 0 **e** média ≥ percentil 95 do placebo P2;
5. robustez: média > 0 com 2× custo e com k = 0,25 e k = 1,0.

**INCONCLUSIVO** se média > 0 no total e nas duas metades **e** acima da média do braço base, do P1 e da mediana do P2, sem passar em todos os critérios do GO.
**NO-GO** nos demais casos.

## 6. Ressalvas declaradas antes
- O braço base foi escolhido como o melhor da fase 20 **nestes mesmos dados** (viés de seleção); por isso o critério 3 (incremento sobre o base) é o centro do teste.
- Poder baixo: o base teve 147 operações (96/51 por metade); o filtro deve cortar perto de metade, então o critério 2 (n ≥ 30 por metade) pode falhar só por tamanho. Isso não será relaxado depois.
- Mesmo com GO nada vai ao vivo: o passo seguinte seria acompanhamento offline por ≥ 40 pregões novos, com nova aprovação do owner.
