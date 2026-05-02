import subprocess

r = subprocess.run(['wmic', 'process', 'where', 'name="python.exe"', 'get', 'ProcessId,CommandLine', '/FORMAT:LIST'], capture_output=True, text=True)
for line in r.stdout.split('\n'):
    if 'collector' in line.lower():
        print(line.strip())
