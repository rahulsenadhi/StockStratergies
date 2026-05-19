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

echo [2/2] Downloading wider NSE/BSE ... >> "%LOG%"
"%PY%" nse_bse_downloader.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! nse_bse_downloader.py FAILED with exit code %ERRORLEVEL% >> "%LOG%"
) else (
    echo  ok NSE/BSE done >> "%LOG%"
)

echo Refresh finished: %DATE% %TIME% >> "%LOG%"
echo ====================================================== >> "%LOG%"

exit /b 0
