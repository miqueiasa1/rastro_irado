import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()
import traceback
try:
    snaps = e.compute_from_db(today, 'WDO$N')
    print('Snapshots:', len(snaps))
except Exception as ex:
    print('Exception in compute_from_db:')
    traceback.print_exc()

print("--- Data Check ---")
bars = e.db.get_session_data(today, 'WDO$N') if hasattr(e, 'db') else []
