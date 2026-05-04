"""
Wrapper para o Teste de Cointegração de Johansen.
"""
import pandas as pd
import warnings
from statsmodels.tsa.vector_ar.vecm import coint_johansen

def check_cointegration(df_basket: pd.DataFrame, det_order: int = 0, k_ar_diff: int = 1) -> tuple[float, bool]:
    """
    Executa o teste de Johansen em uma cesta de ativos para verificar cointegração.
    
    Args:
        df_basket: DataFrame onde cada coluna é a série de preços/retornos de um ativo (Target + Fatores).
        det_order: Ordem da tendência determinística (0 para sem tendência, 1 para linear, -1 sem constante/tendência).
        k_ar_diff: Lags da diferença a incluir no VECM (normalmente 1).
        
    Returns:
        (p_value_aprox, is_cointegrated):
            p_value_aprox é uma aproximação baseada nos valores críticos (0.1, 0.05, 0.01).
            is_cointegrated é True se houver evidência de pelo menos 1 vetor de cointegração a 95% de confiança.
    """
    if len(df_basket) < 20: # Amostra mínima muito pequena para ser confiável
        return 0.05, True # Assume cointegrado para não quebrar no início da sessão
        
    try:
        # Remover colunas com variância zero (evita Singular matrix error em sessões paradas)
        variances = df_basket.var()
        df_valid = df_basket.loc[:, variances > 1e-10]
        
        # Se não houver pelo menos 2 séries com variância, não há como testar cointegração
        if df_valid.shape[1] < 2:
            return 0.05, True # Assume cointegrado (fallback)
            
        # Supressão de warnings para evitar spam no console da API
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = coint_johansen(df_valid, det_order, k_ar_diff)
        
        # Testando a hipótese nula de que o número de vetores de cointegração r = 0.
        # res.lr1: Estatística do traço (Trace statistic) para r=0, r<=1, etc.
        # res.cvt: Tabela de valores críticos para 90%, 95%, 99% (índices 0, 1, 2)
        
        trace_stat = res.lr1[0]
        crit_val_95 = res.cvt[0, 1] # 95% de confiança para r=0
        crit_val_90 = res.cvt[0, 0] # 90%
        crit_val_99 = res.cvt[0, 2] # 99%
        
        # is_cointegrated se a estatística do traço for maior que o valor crítico de 95%
        is_cointegrated = trace_stat > crit_val_95
        
        # Estimativa grosseira do p-value com base nos thresholds
        if trace_stat > crit_val_99:
            p_val = 0.005
        elif trace_stat > crit_val_95:
            p_val = 0.04
        elif trace_stat > crit_val_90:
            p_val = 0.08
        else:
            p_val = 0.20 # Maior que 0.1
            
        return float(p_val), bool(is_cointegrated)
        
    except Exception as e:
        # Em caso de erro numérico (matriz singular, etc)
        # Assumimos que a cointegração se manteve (fallback) para não derrubar o P_UP
        return 0.05, True
