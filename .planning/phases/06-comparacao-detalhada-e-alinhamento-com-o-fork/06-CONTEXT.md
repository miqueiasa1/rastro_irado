# Phase 6: Comparação Detalhada e Alinhamento com o Fork - Context

**Gathered:** 2026-07-24
**Status:** Completed
**Source:** Requisição direta de desenvolvimento para auditoria de repositório fork

<domain>
## Phase Boundary

Esta fase compreende a comparação estrutural, lógica e visual completa entre o branch principal de desenvolvimento local (`main`) e a ramificação principal do fork do projeto (`breno/main` do fork `brenoperucchi/rastro_irado`).

O objetivo é mapear todos os pontos de convergência, divergência e conflitos de mesclagem para preparar a base do merge subsequente sem quebrar as regras de integridade do frontend e do backend operacionais.

</domain>

<decisions>
## Implementation Decisions

### 1. Auditoria Física de Conflitos (COMPAR-01)
- Identificar todos os arquivos modificados e os blocos de conflitos de mesclagem via simulação de merge.
- Registrar os conflitos nos arquivos-chave: `backend/api/main.py`, `backend/irai/engine.py`, `frontend/src/App.jsx`, `frontend/src/Overview.jsx`, `scripts/calibrate_universal.py` e `backend/db.py`.

### 2. Estrutura e Escopo das Frentes Divergentes (COMPAR-02)
- Mapear a migração do frontend Lightweight-charts realizada no fork vs. modularização com GARCH e Basket Z-Score realizada localmente.
- Documentar os impactos no NWE causal com ATR/VWAP sobre barras ghost do fork em relação ao NWE vetorizado no backend.
- Avaliar a suite de testes unitários robusta adicionada pelo fork.

### 3. Registro e Encerramento
- Criar a documentação de artefato `docs/artifacts/irai-6/fork_comparison.md` contendo a tabela comparativa.
- Finalizar a fase como concluída no ROADMAP.md e STATE.md.

</decisions>

<canonical_refs>
## Canonical References

- `docs/artifacts/irai-6/fork_comparison.md` — Relatório canônico da comparação detalhada.
- `AGENTS.md` — Regras do Projeto (Sincronização de zoom horizontal, gráfico de Pair Spread visível).
- `.planning/ROADMAP.md` e `.planning/STATE.md` — Rastreamento de evolução do projeto.

</canonical_refs>

---

*Phase: 06-comparacao-detalhada-e-alinhamento-com-o-fork*
*Context gathered: 2026-07-24*
