import urllib.request, json
r = urllib.request.urlopen('http://localhost:8888/api/irai/series?target=WIN$N', timeout=15)
d = json.loads(r.read())
series = d.get('series', [])
returns = [s.get('win_return', 0) for s in series]
pups = [s.get('p_up', 50) for s in series]
print(f"Barras: {len(series)}")
print(f"win_return: min={min(returns):.3f}% max={max(returns):.3f}%")
print(f"p_up:       min={min(pups):.1f}% max={max(pups):.1f}%")
print(f"\nSymmetric domain [-max, max]:")
max_abs = max(abs(min(returns)), abs(max(returns)), 0.01)
print(f"  win axis: [{-max_abs:.3f}, {max_abs:.3f}] → 0% centered at 50% height")
print(f"  pup axis: [0, 100] → 50% centered at 50% height")
