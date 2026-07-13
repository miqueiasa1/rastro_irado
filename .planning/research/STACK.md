# Stack Research

**Domain:** Quantitative Finance / Intraday Indicators
**Researched:** 2026-07-13
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Runtime do backend | Plataforma existente do backend, compatível com a biblioteca MetaTrader 5 e bibliotecas numéricas de alta performance. |
| NumPy | 1.24+ | Computação numérica vetorizada | Executa operações matemáticas em arrays de forma vetorizada em C, convertendo a complexidade O(n²) do Javascript puro em uma fração de milissegundos. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI | 0.95+ | Endpoint REST | Framework existente para servir a API. Facilita o envio de payloads JSON enriquecidos com NWE. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Testes unitários de paridade | Validar que a implementação em Python/NumPy produz exatamente o mesmo resultado que o Javascript original (tolerância de erro numérico de float < 1e-9). |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| NumPy (Vetorizado) | SciPy (ndimage/convolve) | Útil se precisássemos de filtros de convolução multidimensionais mais complexos. Para kernel gaussiano causal 1D simples, a implementação direta no NumPy é mais leve e rápida. |
| NumPy (Vetorizado) | Pandas (rolling apply) | O Pandas simplifica operações com séries temporais estruturadas, mas o `apply` em janelas móveis com funções customizadas é em Python puro (lento). Vetorização pura com NumPy é muito mais performática. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Cálculos em loops puros do Python (for loops) | Loops puros em Python são mais lentos que o loop JIT do V8 no React, o que anularia os benefícios de mover o cálculo para o backend. | Operações vetorizadas com arrays NumPy ou fatiamentos rápidos (slicing). |

## Sources

- [FastAPI Docs] — https://fastapi.tiangolo.com/
- [NumPy Vectorization Guide] — https://numpy.org/doc/stable/user/absolute_beginners.html
