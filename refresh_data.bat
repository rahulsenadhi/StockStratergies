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

echo [1/9] Downloading Nifty 50 ... >> "%LOG%"
"%PY%" step1_download_data.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! step1_download_data.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok Nifty 50 done >> "%LOG%"
)

echo [2/9] Downloading wider NSE/BSE ... >> "%LOG%"
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

echo [3/9] Rebuilding Momentum Edge parquet cache + backtest ... >> "%LOG%"
"%PY%" momentum_edge_backtest.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! momentum_edge_backtest.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok parquet cache + backtest done >> "%LOG%"
)

echo [4/9] Pre-computing exit recommendations ... >> "%LOG%"
"%PY%" precompute_exit_recommendations.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! precompute_exit_recommendations.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok exit recommendations done >> "%LOG%"
)

echo [5/9] Pre-warming PEAD yfinance cache ... >> "%LOG%"
"%PY%" -c "from concurrent.futures import ThreadPoolExecutor; import pandas as pd; from core.yf_cache import get_snapshot; u = pd.read_csv('data/universe/universe.csv')['yf_ticker'].dropna().tolist(); print(f'Warming {len(u)} tickers'); ex = ThreadPoolExecutor(max_workers=12); list(ex.map(get_snapshot, u)); print('Cache warm')" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! yfinance cache warm FAILED >> "%LOG%"
) else (
    echo  ok cache warm done >> "%LOG%"
)

echo [6/9] PEAD daily incremental refresh ... >> "%LOG%"
"%PY%" pead_downloader.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! pead_downloader.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok PEAD downloader done >> "%LOG%"
)

echo [7/9] Saving Monthly data for the Next.js app ... >> "%LOG%"
"%PY%" precompute_ui_monthly.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! precompute_ui_monthly.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok ui_monthly.json done >> "%LOG%"
)

echo [8/9] Saving Momentum data for the Next.js app ... >> "%LOG%"
"%PY%" precompute_ui_momentum.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! precompute_ui_momentum.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok ui_momentum.json done >> "%LOG%"
)

echo [9/9] Saving Home data for the Next.js app ... >> "%LOG%"
"%PY%" precompute_ui_home.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! precompute_ui_home.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok ui_snapshot.json done >> "%LOG%"
)

echo Refresh finished: %DATE% %TIME% >> "%LOG%"
echo ====================================================== >> "%LOG%"

exit /b 0
