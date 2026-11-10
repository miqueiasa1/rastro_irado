# Phase 18 Summary: Features Causais, Valor Justo da Cesta e Treino Walk-Forward

**Implementada:** 2026-11-10 (worktree `C:\Users\ryzen\Downloads\Antigravity\rastro_irado_wt_f17_18`, branch local `v2/fase-17-18`; sem commit, sem push)
**Status:** Implementada, aguardando aprovação. Pesquisa offline sobre dados lidos em modo somente leitura; nada ligado ao live.

## Veredito
**O valor justo da cesta não dá vantagem mensurável, nem como evento de entrada nem como feature do modelo de 60 min.**
O z causal ficou bem padronizado (é um z de verdade), mas o descolamento não previu o retorno das barras seguintes e
nenhum evento teve P&L líquido de custos que sobrevivesse à correção para testes múltiplos. O p_fwd_60 walk-forward não
passou nos critérios pré-registrados. Nada bate a taxa-base nem as baselines momentum/contrarian.

## Results Summary

### Valor justo da cesta (`data/reports/fase18_valor_justo_20261110.md`)
482 pregões (02/12/2024–10/11/2026); desenho até 31/12/2025, validação em 2026; 7 variantes; 336 testes por parte.
- **O z agora é um z:** |z| > 2 em 4,4% (desenho) e 8,0% (validação) das barras no WIN (`cesta_w60`) e 4,1% / 5,5% no
  WDO; desvio do z 0,97–1,12. A construção atual dá 54–58% (`par_ols20_z_atual`) e o z ao vivo gravado, 31–37%.
- **Não prevê:** AUC de −z contra o sinal de 15/30/60 min entre 0,49 e 0,51 em todas as variantes (a melhor, WDO
  `cesta_w60_movel40` a 15 min: 0,52 nos dois períodos). Baselines do retorno do dia em 60 min: WIN momentum
  0,507 / 0,502; WDO contrarian 0,490 / 0,522.
- **Eventos (z ≥ 2, contrarian, 60 min, líquido):** WIN `cesta_w60` −88 pts (t −1,42) no desenho e +232 pts
  (IC 3,9 a 506; t 1,74) na validação — sinal trocado entre períodos; q (BH) 0,36. WDO `cesta_w60` −1,3 pt e +1,0 pt.
- **O gap raramente fecha:** |z| volta abaixo de 0,5 em 0–8% dos eventos em 60 min e em 15–27% até o fechamento
  (variantes com σ do perfil); quando fecha, ~0,8–1,2 do fechamento vem do próprio alvo (o preço vai até o valor justo,
  não o contrário). São ~0,3–0,7 eventos por pregão.
- **Testes múltiplos:** desenho 22 e validação 35 testes com q (BH) < 0,05 — **todos com P&L líquido negativo**
  (sobretudo seguir o gap no WDO, que perde o custo). Nenhum teste positivo passa BH ou Bonferroni.
- **Reversão pequena no WDO:** `cesta_w60_movel40` contrarian a 15 min tem bruto estável de +0,4 a +0,6 pt nos dois
  períodos, abaixo do custo de 1 pt (líquido −0,4 a −0,6).

### Modelo de 60 min (`data/reports/fase18_p_fwd_60_walkforward_20261110.md`)
Walk-forward mensal desde 2025-06 (1º bloco com 80 pregões de treino), 361 pregões fora da amostra por alvo,
config pré-registrada (hash `034caeb69793`).
- **WIN:** A AUC 0,496 (0,481–0,510), BSS −0,0003; B 0,499 (0,484–0,514), BSS −0,0003; C 0,496, BSS −0,0010.
- **WDO:** A 0,501 (0,487–0,515), BSS −0,0007; B 0,501, BSS −0,0007; C 0,483 (0,467–0,498), BSS −0,0021.
- ECE ≤ 1 pp em todos no período fora da amostra inteiro — porque o modelo aprende a não opinar (p entre 45% e 55% em > 99% das barras).
- B − A (o valor justo acrescentado): ΔAUC +0,003 (IC −0,004 a +0,010) no WIN e +0,0002 no WDO; ΔBSS ≈ 0.
- Decisão pré-registrada: **rejected** nos dois (BSS < 0 e IC da AUC contém 0,5). Nenhuma versão `forecast` registrada.

### Harness diário (fase 15 → `HARNESS_VERSION` 18.0)
Novo bloco no JSON e no relatório: cobertura de |z| > 2 e P&L por evento dos z gravados ao vivo. Na baseline
(03/08–10/11, corte 10/11 13:50 UTC, cópia do banco): WIN `pair_fixed_z` 32,3% de cobertura, 207 eventos,
+17,8 pts líquidos a 60 min (IC −125,8 a 138,6); `pair_z` 34,0%, −11,3 pts; `price_diverge_z` 30,7%, −10,2 pts. WDO 32–36%
de cobertura e −0,6 a +0,5 pt. As métricas da baseline da fase 15 continuam reproduzidas (AUC 60 min 0,474 / 0,486).

## Critérios
1. Testes de causalidade e de split verdes — **atingido** (`test_features_causal.py` 10, `test_walkforward_split.py` 3,
   `test_events.py` 4).
2. BSS ≥ 0 e ECE ≤ 3 pp em 60 min [META] — **não atingido** (ECE sim, BSS não).
3. AUC de 60 min ≥ protótipo dentro do IC (WIN 0,540; WDO 0,503) — WIN não (0,499, IC até 0,514); WDO sim no ponto
   (0,501 contra 0,503, que já era sem sinal). Por ativo: nenhum dos dois tem chance de passar no go/no-go com estas
   features.
4. Versão registrada — não registrada (rejeitada); ver decisões.

## Verificação
- Suíte completa numa cópia isolada (`%TEMP%\irai_p1718\suite`): **112 passed**.
- Os números vêm de `scripts/research_fair_value.py` (hash `7d474b00a0ca`) e `scripts/train_forecast.py`
  (hash `034caeb69793`) sobre a exportação somente leitura de 10/11/2026; relatórios gerados por
  `scripts/render_fase18_reports.py`.

## Ativação (pendente de aprovação)
- Não há nada para ligar ao vivo nesta fase. Com o código no branch em produção, a tarefa "IRAI Daily Assertividade"
  passa a incluir o bloco de cobertura/P&L por evento automaticamente.

## Em aberto (decisão do owner)
1. Registrar o p_fwd_60 como versão `forecast` com status `rejected` no `irai_live.db` (trilha de auditoria) ou só o relatório.
2. A reversão pequena do WDO (+0,4–0,6 pt bruto, abaixo do custo): descartar ou só acompanhar no harness.
3. O +232 pts do WIN em 2026 (contrarian 60 min) não se sustenta no desenho nem nos testes múltiplos: acompanhar em
   shadow na fase 19 ou descartar.
4. Seguir para a fase 19 (shadow ao vivo) só com o nowcast corrigido, ou parar e aplicar a D3 (`nowcast_only`) direto.

## Key Files
- Novos: `backend/irai/features.py`, `backend/eval/events.py`, `backend/eval/walkforward.py`,
  `scripts/research_fair_value.py`, `scripts/train_forecast.py`, `scripts/render_fase18_reports.py`,
  `tests/f18_fixtures.py`, `tests/test_features_causal.py`, `tests/test_walkforward_split.py`, `tests/test_events.py`,
  `data/reports/fase18_valor_justo_20261110.md`, `data/reports/fase18_p_fwd_60_walkforward_20261110.md`,
  `data/reports/fase17_correcao_beta_z_20261110.md`, `data/eval/fase18/*.json`
- Alterados: `backend/eval/__init__.py`, `backend/eval/data.py`, `backend/eval/harness.py`, `backend/eval/report.py`
