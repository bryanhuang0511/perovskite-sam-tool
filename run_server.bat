@echo off
chcp 65001 > nul
echo ========================================================
echo   鈣鈦礦 SAM 論文數據與 DOI 擷取工具 (Perovskite SAM Extractor)
echo ========================================================
echo.
echo 啟動 Python 虛擬環境與 FastAPI 伺服器...
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
pause
