---
title: Reordenar caminhos do MT5 no coletor para evitar IPC timeout
date: 2026-07-12
priority: high
---

Colocar o caminho de fallback funcional do terminal B3 (XP) (`C:\Program Files\MetaTrader 5\terminal64.exe`) em primeiro lugar na lista do `backend/workers/collector.py` para remover o atraso de 5 segundos de IPC timeout em cada ciclo de coleta.
