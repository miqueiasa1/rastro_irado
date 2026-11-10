"""
Splits walk-forward com purge e embargo por sessão (fase 18, SPEC §6).

- Externo: blocos mensais de teste; treino = sessões com data < início do bloco, menos as
  `embargo` sessões imediatamente anteriores ao teste. Alvo intradiário (não cruza o pregão),
  então o purge equivale a excluir sessões ≥ início do teste.
- Interno: K dobras contíguas por sessão dentro do treino, com `embargo` sessões removidas de
  cada lado da dobra de validação.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Split:
    test_label: str
    train_sessions: tuple
    test_sessions: tuple


def monthly_splits(sessions, first_test_month: str, embargo: int = 1, min_train: int = 60,
                   rolling: int | None = None) -> list[Split]:
    """Blocos mensais a partir de `first_test_month` (AAAA-MM). `rolling`: janela móvel de treino."""
    ss = sorted(set(sessions))
    months = sorted({s[:7] for s in ss if s[:7] >= first_test_month})
    out = []
    for m in months:
        test = tuple(s for s in ss if s[:7] == m)
        if not test:
            continue
        before = [s for s in ss if s < test[0]]
        train = before[:-embargo] if embargo > 0 else before
        if rolling:
            train = train[-rolling:]
        if len(train) < min_train:
            continue
        out.append(Split(m, tuple(train), test))
    return out


def purged_kfold(train_sessions, k: int = 5, embargo: int = 2) -> list[tuple[tuple, tuple]]:
    """(treino, validação) por dobra contígua, com embargo de `embargo` sessões em volta."""
    ss = list(train_sessions)
    n = len(ss)
    folds = np.array_split(np.arange(n), k)
    out = []
    for f in folds:
        if len(f) == 0:
            continue
        lo, hi = f[0], f[-1]
        val = tuple(ss[lo:hi + 1])
        tr = tuple(ss[:max(0, lo - embargo)] + ss[hi + 1 + embargo:])
        out.append((tr, val))
    return out
