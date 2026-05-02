import sys
sys.path.insert(0, '.')
from backend.irai.engine import resolve_symbol
print('RESOLVED WIN$N =', repr(resolve_symbol('WIN$N')))
