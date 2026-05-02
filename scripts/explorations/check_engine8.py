import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()

target = 'WDO$N'
snaps = e.compute_from_db(today, target)
print("Snapshots:", len(snaps))
