import urllib.request, json
url = 'http://localhost:8888/api/irai/series?target=WDO%24N'
try:
    req = urllib.request.urlopen(url)
    data = json.loads(req.read().decode('utf-8'))
    print('WDO$N Bars:', len(data.get('series', [])))
except Exception as e:
    print('Exception:', e)
