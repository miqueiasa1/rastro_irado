import sys, os
sys.path.append(r"c:\Users\ryzen\Downloads\Antigravity\rastro_irado")
from backend.irai.engine import IRAIEngine

engine = IRAIEngine()
snaps = engine.compute_from_db("2026-04-30", "WIN$N")
if snaps:
    snap = snaps[-1]
    print(f"Snap score: {snap.score}")
    print(f"P_up: {snap.p_up}")
else:
    print("No snaps")
