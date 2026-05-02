import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()
snaps = e.compute_from_db(today, 'WIN$N')
print(f'Length of snaps: {len(snaps)}')
