@echo off
set PATH=C:\Users\ryzen\AppData\Roaming\Python\Python313\Scripts;%PATH%
set PYTHONPATH=C:\Users\ryzen\AppData\Roaming\Python\Python313\site-packages;%PYTHONPATH%
C:\Python313\python.exe -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8888
