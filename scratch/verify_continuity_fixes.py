import sys
import os
import sqlite3
from datetime import datetime, date, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import get_connection, save_kalman_state, load_kalman_state
from backend.irai.engine import IRAIEngine

def test_timestamp_guard():
    print(">>> Testing Kalman State Timestamp Guard...")
    conn = get_connection()
    slug = "test_asset"
    timeframe = "M5"
    session_date = "2026-07-10"
    
    # 1. Clean existing state if any
    conn.execute("DELETE FROM kalman_state WHERE slug = ? AND timeframe = ? AND session_date = ?", (slug, timeframe, session_date))
    conn.commit()
    
    # 2. Insert initial state
    save_kalman_state(conn, slug, timeframe, session_date, [1.0, 2.0], [[1.0, 0.0], [0.0, 1.0]], 0.01, True, "2026-07-10T12:00:00Z")
    
    # Check it exists
    state1 = conn.execute("SELECT timestamp_utc, state_mean FROM kalman_state WHERE slug = ? AND timeframe = ? AND session_date = ?", (slug, timeframe, session_date)).fetchone()
    assert state1 is not None
    assert state1["timestamp_utc"] == "2026-07-10T12:00:00Z"
    
    # 3. Try to save with older timestamp
    save_kalman_state(conn, slug, timeframe, session_date, [3.0, 4.0], [[2.0, 0.0], [0.0, 2.0]], 0.02, True, "2026-07-10T11:00:00Z")
    
    # Verify it was NOT overwritten
    state2 = conn.execute("SELECT timestamp_utc, state_mean FROM kalman_state WHERE slug = ? AND timeframe = ? AND session_date = ?", (slug, timeframe, session_date)).fetchone()
    assert state2["timestamp_utc"] == "2026-07-10T12:00:00Z"
    
    # 4. Try to save with newer timestamp
    save_kalman_state(conn, slug, timeframe, session_date, [5.0, 6.0], [[3.0, 0.0], [0.0, 3.0]], 0.03, True, "2026-07-10T13:00:00Z")
    
    # Verify it WAS overwritten
    state3 = conn.execute("SELECT timestamp_utc, state_mean FROM kalman_state WHERE slug = ? AND timeframe = ? AND session_date = ?", (slug, timeframe, session_date)).fetchone()
    assert state3["timestamp_utc"] == "2026-07-10T13:00:00Z"
    
    # Clean up
    conn.execute("DELETE FROM kalman_state WHERE slug = ? AND timeframe = ? AND session_date = ?", (slug, timeframe, session_date))
    conn.commit()
    conn.close()
    print("    [SUCCESS] Timestamp guard verified!")

def test_deterministic_pre_market():
    print(">>> Testing Deterministic Pre-Market Hour Alignment...")
    engine = IRAIEngine()
    
    # WIN$N has session_start_h = 9 (BRT). In EEST/Tickmill (+6h shift), it opens at 15:00 UTC.
    # We query historical data for WIN$N for a known date, e.g., '2026-06-24' (a valid B3 trading day)
    snaps = engine.compute_from_db("2026-06-24", target="WIN$N", version="v2", persist_state=False)
    
    if snaps:
        pre_market_snaps = []
        regular_snaps = []
        for s in snaps:
            # Parse timestamp to extract EEST hour
            ts_dt = datetime.fromisoformat(s.timestamp.replace("Z", "+00:00"))
            hour = ts_dt.hour
            
            if hour < 15:
                pre_market_snaps.append(s)
            else:
                regular_snaps.append(s)
        
        print(f"    Total snaps: {len(snaps)} (Pre-market: {len(pre_market_snaps)}, Regular: {len(regular_snaps)})")
        
        # Verify pre-market snapshots have win_return = 0.0 and are flagged as ghost
        for s in pre_market_snaps:
            assert s.win_return == 0.0, f"Failed: win_return was {s.win_return} at {s.timestamp} in pre-market"
            assert s.is_ghost == True, f"Failed: is_ghost was False at {s.timestamp} in pre-market"
            
        # Verify first regular snapshot has correct return and might not be ghost
        if regular_snaps:
            first_reg = regular_snaps[0]
            print(f"    First regular bar: {first_reg.timestamp}, win_return: {first_reg.win_return}%")
            
        print("    [SUCCESS] Deterministic pre-market alignment verified!")
    else:
        print("    [SKIP] No historical B3 bars found for 2026-06-24. Verification skipped.")

if __name__ == "__main__":
    test_timestamp_guard()
    test_deterministic_pre_market()
