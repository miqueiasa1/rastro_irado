import subprocess

r = subprocess.run(['wmic', 'process', 'where', 'name="python.exe"', 'get', 'ProcessId,CommandLine', '/FORMAT:LIST'], capture_output=True, text=True)
for line in r.stdout.split('\n'):
    if '.py' in line.lower() and 'wmic' not in line.lower():
        print(line.strip())
