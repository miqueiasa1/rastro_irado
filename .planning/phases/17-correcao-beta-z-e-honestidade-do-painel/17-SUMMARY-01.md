# Phase 17 Summary: Correção β/z e Honestidade do Painel

**Implementada:** 2026-11-10 (worktree `C:\Users\ryzen\Downloads\Antigravity\rastro_irado_wt_f17_18`, branch local `v2/fase-17-18`, criada de `v2/fase-16-versionamento`; sem commit, sem push)
**Status:** Implementada, aguardando aprovação de commit e ativação. Nada foi gravado no `data\irai_live.db`, nenhum serviço foi reiniciado e a pasta de produção continua em `v2/fase-16-versionamento` @ `090fdf5`.

## Results Summary
- **Score corrigido (REQ-M01):** com `unit_fix=1` a contribuição de cada fator é β·σ·z ÷ `score_scale`
  (= β·r ÷ desvio de Σ β·r no treino). `score_scale`: WIN 0,0055; WDO 0,0043.
- **α/intercepto sem clamp (REQ-M02):** logística sobre o score corrigido. WIN α 1,354, b +0,148; WDO α 1,243, b −0,390
  (as versões ativas tinham α = 1,0 no limite do clamp; WDO b = −0,25 no limite).
- **Kalman (REQ-M04):** R = variância do resíduo intradiário: WIN 0,569 %², WDO 0,150 %² (antes 1e-3);
  Q = deriva dos β de janelas de 20 pregões: WIN 4,8e-5, WDO 2,8e-5 por barra (antes 1e-5).
- **Compatibilidade:** são opções da versão (`unit_fix`, `score_scale`, `kalman_obs_cov`, `kalman_trans_cov`); sem elas
  o cálculo é o antigo. Verificado numa cópia do banco: código novo × código de produção, 5 alvos × 5 pregões
  (04–10/11), 6.981 barras, **ΔP máximo = 0**.
- **Versões corrigidas:** `scripts/fase17_unit_fix.py` mantém fatores, β e σ das versões ativas de 28/10 e só corrige o
  bug, na mesma janela (16/10/2025–28/10/2026, 252 pregões). Registradas como `shadow` **só nas cópias**
  (box e `%TEMP%\irai_p1718\suite`).
- **API (REQ-A04):** `/api/irai/targets` com `calibrated` (pesos carregados, independente de `accuracy`),
  `model_version`, `forecast_mode`, `forecast_ui`; `forecast_ui` no card do overview e no `summary` da série; overview
  filtra por `calibrated` (hoje os 14 alvos ativos têm acurácia, então a lista não muda).
- **Painel (REQ-U04), só com `forecast_ui` ∈ {`on`, `nowcast_only`}:** "Leitura do dia (nowcast)" no lugar de
  "Rastro Macro" ("dia em alta/baixa"); z de spread/par/macro descritivo ("bem acima/abaixo da ref."), sem COMPRA/VENDA;
  convicção sem a acurácia; rodapé do card sem "acc"; fatores "puxa ↑/↓". O gráfico do z do par continua (Regra 1).
  Com `off` (padrão de todos os alvos) a UI é a atual.

## Critérios
1. **Score corrigido reproduz o regressor:** a AUC do score corrigido é exatamente a do regressor (WIN 0,775; WDO 0,770,
   contra 0,762 e 0,706 do score antigo). Acurácia com P > 50%: WDO 65,1% → 70,2% (regressor 76,2% com o intercepto
   da regressão, 69,0% sem); WIN 71,4% → 70,6% (regressor 71,0%). A diferença restante vem do intercepto: a logística
   escolhe o b que melhor calibra, não o que reproduz o corte do regressor. **Parcial** (ver decisões).
   O alvo do PHASES (WDO 73,0%) era de outra janela.
2. **BSS do nowcast corrigido ≥ atual nas mesmas barras [META] — atingido.** Recálculo 03/08–10/11 (69 pregões, ~7.760
   barras, Kalman do zero nos dois): WIN AUC 0,774 → 0,828, BSS 0,165 → 0,266; WDO AUC 0,757 → 0,869, BSS 0,147 → 0,261.
   Fora da amostra da calibração (29/10–10/11, 9 pregões): WIN BSS 0,390 → 0,512; WDO −1,200 → −0,909 (os dois mal
   calibrados nesse trecho, ECE ~31 pp). Em 60 min os dois continuam sem previsão (BSS WIN −0,25 → −0,30;
   WDO −0,17 → −0,24): o nowcast descreve o dia, não prevê.
3. **Sem "acc" na UI:** atendido com `forecast_ui` ligado; o site público só muda com deploy aprovado.
4. **Todos os alvos no overview:** atendido (filtro por `calibrated`).

## Verificação
- Suíte completa numa cópia isolada (`%TEMP%\irai_p1718\suite`, com cópia do banco via backup API): **112 passed**
  (87 anteriores + 25 novos; desta fase: `tests/test_unit_fix.py`, 8).
- Relatório: `data/reports/fase17_correcao_beta_z_20261110.md`; resumo: `data/eval/fase18/fase17_20261110.json`.

## Ativação (pendente de aprovação do owner)
1. Commit na branch `v2/fase-17-18` (sem push) e decidir como a pasta de produção passa a rodar esse código
   (checkout da branch na pasta do repo ou merge). Só o código, com flags `off` e sem promoção, não muda o P (ΔP = 0).
2. Backup do banco e registro das versões corrigidas (só INSERT):
   `C:\Python313\python.exe scripts\fase17_unit_fix.py --db data\irai_live.db --register-db data\irai_live.db`
3. Promover para uma sessão futura, depois do pregão:
   `C:\Python313\python.exe scripts\model_versions.py promote <id> --effective-from AAAA-MM-DD` (WIN e WDO).
   O estado do Kalman reinicia na troca de versão (fase 16).
4. Ligar o painel honesto: `UPDATE asset_models SET forecast_ui = 'nowcast_only' WHERE target IN ('WIN$N','WDO$N')`.
5. Reiniciar `IRAI_API`, `IRAI_Collector` e `IRAI_FirebaseSync` (o `IRAI_Frontend` recarrega sozinho).
   O site público (Firebase) não muda até um deploy aprovado.
- Reverter: `promote` da versão anterior para a próxima sessão e `forecast_ui = 'off'`.

## Em aberto (decisão do owner)
1. Promover as versões corrigidas junto com `forecast_ui='nowcast_only'` (recomendado: o P corrigido é mais extremo,
   P < 20 ou > 80 em 24% das barras do WIN contra 20%).
2. Intercepto: manter o da logística (melhor calibração) ou forçar o corte do regressor (acurácia igual à dele).
3. `forecast_ui` dos demais alvos (fora do v2.0 pela D2): continuam com "acc" e COMPRA/VENDA de z.
4. Rótulo "coint ✓/✗" (Johansen) no rodapé do card: WIN×WDO não é cointegrado; esconder no modo honesto?
5. Recalibrar os demais alvos com `calibrate_universal.py` (já grava a versão corrigida, sempre em shadow).

## Key Files
- Novos: `backend/irai/nowcast_calib.py`, `scripts/fase17_unit_fix.py`, `scripts/compare_nowcast_versions.py`,
  `frontend/src/utils/honesty.js`, `tests/test_unit_fix.py`
- Alterados: `backend/irai/model_registry.py`, `backend/irai/engine.py`, `backend/api/main.py`,
  `scripts/calibrate_universal.py`, `frontend/src/App.jsx`, `frontend/src/Overview.jsx`,
  `frontend/src/components/SignalGauge.jsx`, `frontend/src/hooks/useIraiData.js`, `frontend/src/utils/signalAnalyzer.js`,
  `docs/API.md`
