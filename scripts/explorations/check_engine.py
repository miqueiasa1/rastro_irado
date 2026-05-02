import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()
snaps = e.compute_from_db(today, 'WDO$N')
print('Snapshots:', len(snaps))
if not snaps:
    print('Why no snapshots?')
    bars = e.db.get_session_data(today, 'WDO$N')
    print('Bars loaded from DB:', len(bars))
    if len(bars) > 0:
        print('First bar time:', bars[0].timestamp_utc)
        print('Last bar time:', bars[-1].timestamp_utc)
