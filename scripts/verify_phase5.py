"""Script de verificação da Fase 5 — Expansão de Ativos Globais."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import DB_PATH, get_connection
from backend.irai.engine import IRAIEngine

def main():
    print("=== Verificação da Fase 5: Expansão de Ativos Globais ===")
    
    if not os.path.exists(DB_PATH):
        print(f"Erro: Banco de dados {DB_PATH} não encontrado!")
        sys.exit(1)
        
    engine = IRAIEngine(db_path=DB_PATH)
    targets = [t["target"] for t in engine.registered_targets]
    print(f"Total de alvos carregados no Engine: {len(targets)}")
    
    new_assets = ["DE40", "US2000", "JP225", "CHINA50"]
    missing = []
    
    for asset in new_assets:
        target_info = next((t for t in engine.registered_targets if t["target"] == asset), None)
        if target_info:
            acc = f"{target_info.get('accuracy', 0):.1f}%" if target_info.get("accuracy") else "Pendente"
            r2 = f"{target_info.get('r_squared', 0):.4f}" if target_info.get("r_squared") else "N/A"
            factors_count = len(target_info.get("factors", []))
            print(f"  [OK] Asset {asset:10s} | Display: {target_info.get('display_name'):15s} | Accuracy: {acc:8s} | R²: {r2:8s} | Fatores: {factors_count}")
        else:
            print(f"  [FALHA] Asset {asset:10s} não encontrado no Engine!")
            missing.append(asset)

    if missing:
        print(f"\n[ERRO] Ativos ausentes no engine: {missing}")
        sys.exit(1)

    print("\n[SUCESSO] Todos os 4 novos índices globais foram integrados e estão visíveis no IRAIEngine!")

if __name__ == "__main__":
    main()
