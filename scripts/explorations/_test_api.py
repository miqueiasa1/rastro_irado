import requests
r = requests.get('http://localhost:8888/api/irai/overview')
data = r.json()
print('session_date:', data.get('session_date'))
for t in data.get('targets', []):
    print(f"  {t['target']}: p_up={t['p_up']} verdict={t['verdict']} bars={t['bars']}")
