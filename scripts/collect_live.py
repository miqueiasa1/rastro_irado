"""
IRAI — Coleta ao vivo (loop).
Roda collect_history a cada N segundos para manter o banco atualizado.

Uso:
    python scripts/collect_live.py             # intervalo padrao: 300s (5min)
    python scripts/collect_live.py --interval 60
"""
import os, sys, time, argparse, subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["PYTHONIOENCODING"] = "utf-8"

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "collect_history.py")

def run_collect(days=2):
    """Roda o coletor uma vez com --days 2 (apenas últimas 2 sessões)."""
    result = subprocess.run(
        [sys.executable, SCRIPT, "--days", str(days), "--timeframe", "M5"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    # Filtrar só linhas relevantes
    lines = result.stdout.splitlines()
    inserted_total = 0
    for line in lines:
        if "inseridas" in line or "CONCLU" in line or "FALHA" in line or "Conectado" in line:
            print(f"  {line.strip()}")
        if "inseridas" in line:
            try:
                n = int(line.strip().split("inseridas")[0].split(",")[-1].strip())
                inserted_total += n
            except:
                pass
    if result.returncode != 0:
        print(f"  [ERRO] collector retornou {result.returncode}")
        for line in result.stderr.splitlines()[-5:]:
            print(f"    {line}")
    return inserted_total

def main():
    parser = argparse.ArgumentParser(description="IRAI - Coleta ao vivo (loop)")
    parser.add_argument("--interval", type=int, default=300, help="Intervalo entre coletas em segundos (default: 300)")
    parser.add_argument("--days", type=int, default=2, help="Janela de coleta em dias (default: 2)")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"  IRAI — Coleta ao vivo")
    print(f"  Intervalo: {args.interval}s | Janela: {args.days} dias")
    print(f"  Pressione Ctrl+C para parar")
    print(f"{'='*60}")

    cycle = 0
    while True:
        cycle += 1
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] Ciclo #{cycle}")
        try:
            n = run_collect(args.days)
            print(f"  Total inseridas: {n} barras")
        except Exception as e:
            print(f"  [EXCECAO] {e}")

        print(f"  Proxima coleta em {args.interval}s...")
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
