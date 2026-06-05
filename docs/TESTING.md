# Testes — IRAI

## Estratégia Atual

O IRAI não possui uma suíte de testes automatizada formal. A validação é feita por:

### Validação de Calibração

O script `calibrate_universal.py` reporta métricas por target:
- **Acurácia direcional:** % de acertos na direção do retorno
- **R² (coeficiente de determinação):** Qualidade do ajuste do modelo
- **Número de sessões:** Volume de dados usados

```bash
python scripts/calibrate_universal.py
```

Output esperado:
```
WIN$N: accuracy=0.68, R²=0.31, sessions=30
US500: accuracy=0.72, R²=0.28, sessions=30
...
```

### Verificação de Integridade

```bash
# Verificar barras no banco
python test_db.py

# Verificar engine
python scripts/_test_engine.py

# Health check da API
curl http://localhost:8888/api/health
```

### Validação Manual do Frontend

1. Abrir http://localhost:5175
2. Verificar overview multi-ativo (todos os ativos com dados)
3. Selecionar cada ativo e conferir:
   - Gráfico P(↑) com zonas coloridas
   - Gráfico de movimento com preço, NWE, sessões
   - GEX levels visíveis (toggle GEX ativo)
   - Heatmap de sinais
4. Testar navegação entre datas
5. Verificar WebSocket (dados atualizam em tempo real)

## Testes Recomendados

Áreas que se beneficiariam de testes automatizados:

| Área | Tipo | Prioridade |
|------|------|------------|
| `engine.compute_from_db()` | Unit | Alta — lógica core do P(↑) |
| `kalman.py` filter_update | Unit | Alta — convergência do filtro |
| `johansen.py` | Unit | Média — cointegração |
| API endpoints | Integration | Média — respostas e cache |
| Collector MT5 | Manual | Baixa — depende de MT5 ativo |
| GEX parsing | Unit | Baixa — dados estáticos |

## Validação de GEX

Para verificar que os GEX levels foram extraídos corretamente:

```bash
python scripts/sync_gex_to_irai.py
# Deve reportar 306 níveis para 11 ativos
```
