@echo off
REM ─────────────────────────────────────────────────────────────────────
REM  NSE Strategy Hub — daily data refresh
REM  Runs both downloaders, logs output, marked timestamps.
REM  Invoked by Windows Task Scheduler. Safe to run manually too.
REM ─────────────────────────────────────────────────────────────────────

set "PROJ=C:\Users\User\Documents\Stocks\Nifty Momentum Rotation Stratergy"
set "PY=C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe"
set "LOG=%PROJ%\refresh_log.txt"

cd /d "%PROJ%"

echo. >> "%LOG%"
echo ====================================================== >> "%LOG%"
echo  Refresh started: %DATE% %TIME% >> "%LOG%"
echo ====================================================== >> "%LOG%"

echo [1/2] Downloading Nifty 50 ... >> "%LOG%"
"%PY%" step1_download_data.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! step1_download_data.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok Nifty 50 done >> "%LOG%"
)

echo [2/3] Downloading wider NSE/BSE ... >> "%LOG%"
"%PY%" nse_bse_downloader.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! nse_bse_downloader.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok NSE/BSE done >> "%LOG%"
)

echo [2b] Syncing Parquet store ... >> "%LOG%"
"%PY%" convert_to_parquet.py --sync nse_bse >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! convert_to_parquet.py FAILED >> "%LOG%"
) else (
    echo  ok parquet sync done >> "%LOG%"
)

echo [3/5] Rebuilding Momentum Edge parquet cache + backtest ... >> "%LOG%"
"%PY%" momentum_edge_backtest.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! momentum_edge_backtest.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok parquet cache + backtest done >> "%LOG%"
)

echo [4/5] Pre-computing exit recommendations ... >> "%LOG%"
"%PY%" precompute_exit_recommendations.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! precompute_exit_recommendations.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok exit recommendations done >> "%LOG%"
)

echo [5/6] Pre-warming PEAD yfinance cache ... >> "%LOG%"
"%PY%" -c "from concurrent.futures import ThreadPoolExecutor; import pandas as pd; from core.yf_cache import get_snapshot; u = pd.read_csv('data/universe/universe.csv')['yf_ticker'].dropna().tolist(); print(f'Warming {len(u)} tickers'); ex = ThreadPoolExecutor(max_workers=12); list(ex.map(get_snapshot, u)); print('Cache warm')" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! yfinance cache warm FAILED >> "%LOG%"
) else (
    echo  ok cache warm done >> "%LOG%"
)

echo [6/6] PEAD daily incremental refresh ... >> "%LOG%"
"%PY%" pead_downloader.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! pead_downloader.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok PEAD downloader done >> "%LOG%"
)

echo Refresh finished: %DATE% %TIME% >> "%LOG%"
echo ====================================================== >> "%LOG%"

exit /b 0
