"""
NSE Strategy Hub — One-Click Launcher
Runs all three strategy pipelines then opens all four dashboards.

Usage:
    python run_all.py              # update data + launch all dashboards
    python run_all.py --dash-only  # skip data update, just launch dashboards
    python run_all.py --data-only  # update data only, don't launch dashboards
"""

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Force UTF-8 on Windows so box-drawing characters print correctly
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

PORTS = {
    'Master Hub':         8500,
    'Monthly Rotation':   8501,
    'IPO Edge':           8502,
    'Momentum Edge':      8503,
}

DASHBOARDS = {
    'Master Hub':         'master_dashboard.py',
    'Monthly Rotation':   'dashboard_visual.py',
    'IPO Edge':           'ipo_edge_dashboard.py',
    'Momentum Edge':      'momentum_edge_dashboard.py',
}

# Download scripts stream live output so the user can see progress.
# Backtest scripts capture output and print a summary on completion.
STREAMING_SCRIPTS = {
    'step1_download_data.py',
    'ipo_edge_downloader.py',
    'nse_bse_downloader.py',
    'momentum_edge_downloader.py',
    'build_universe.py',
}

PIPELINES = {
    'Monthly Rotation': [
        [PY, 'step1_download_data.py'],
        [PY, 'step2_backtest_momentum.py'],
        [PY, 'step3_dashboard.py'],
    ],
    'IPO Edge': [
        [PY, 'ipo_edge_downloader.py'],
        [PY, 'ipo_edge_backtest.py'],
    ],
    'Momentum Edge': [
        [PY, 'build_universe.py'],
        [PY, 'nse_bse_downloader.py'],
        [PY, 'momentum_edge_backtest.py'],
    ],
}

W = 70


def sep(ch='─'):
    return ch * W


def _script_name(cmd: list[str]) -> str:
    return next((Path(c).name for c in cmd if c.endswith('.py')), cmd[-1])


def run_step_streaming(cmd: list[str], label: str) -> bool:
    """
    Run a command and stream its stdout/stderr live to the terminal.
    Returns True on success, False on failure.
    Handles Ctrl+C by terminating the child process cleanly.
    """
    print(f'\n     ┌─ {label} (live output) ─────────────────')
    proc = subprocess.Popen(
        cmd, cwd=BASE_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
        encoding='utf-8', errors='replace',
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
    )
    try:
        for line in proc.stdout:
            print(f'     │ {line}', end='', flush=True)
        proc.wait()
    except KeyboardInterrupt:
        print(f'\n     │ [Ctrl+C received — stopping {label}]')
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise   # re-raise so the outer handler can decide to continue or exit

    if proc.returncode == 0:
        print(f'     └─ OK\n')
        return True
    else:
        print(f'     └─ FAILED (exit code {proc.returncode})\n')
        return False


def run_step_captured(cmd: list[str], label: str) -> bool:
    """
    Run a command, capture output, show only on failure.
    For fast backtest scripts where silent output is fine.
    Handles Ctrl+C cleanly.
    """
    print(f'     Running: {label} …', end=' ', flush=True)
    proc = subprocess.Popen(
        cmd, cwd=BASE_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8', errors='replace',
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
    )
    try:
        stdout, stderr = proc.communicate()
    except KeyboardInterrupt:
        print('INTERRUPTED')
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise

    if proc.returncode == 0:
        print('OK')
        return True
    else:
        print('FAILED')
        combined = (stderr or stdout or '')[-800:]
        if combined.strip():
            print(f'\n     --- error output ---\n{combined}\n     --------------------')
        return False


def run_pipeline(name: str, commands: list[list[str]]) -> bool:
    """Run all commands in a pipeline. Returns True if all succeeded."""
    print(f'\n  ▶  {name}')
    for cmd in commands:
        label = _script_name(cmd)
        try:
            if label in STREAMING_SCRIPTS:
                ok = run_step_streaming(cmd, label)
            else:
                ok = run_step_captured(cmd, label)
        except KeyboardInterrupt:
            print(f'\n  ⚠  {name} interrupted by user.')
            return False
        if not ok:
            return False
    return True


def is_port_free(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0


def launch_dashboards() -> list[subprocess.Popen]:
    procs = []
    # Credentials file so Streamlit doesn't ask for email
    creds = Path.home() / '.streamlit' / 'credentials.toml'
    creds.parent.mkdir(exist_ok=True)
    if not creds.exists():
        creds.write_text('[general]\nemail = ""\n')

    for name, script in DASHBOARDS.items():
        port = PORTS[name]
        if not is_port_free(port):
            print(f'  SKIP  {name:<22} port {port} already in use')
            continue
        cmd = [
            PY, '-m', 'streamlit', 'run', script,
            '--server.port', str(port),
            '--server.headless', 'true',
            '--browser.gatherUsageStats', 'false',
        ]
        proc = subprocess.Popen(cmd, cwd=BASE_DIR,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        procs.append(proc)
        print(f'  STARTED  {name:<22} → http://localhost:{port}')

    return procs


def wait_for_dashboards(timeout: int = 25):
    import urllib.request
    deadline = time.time() + timeout
    pending = dict(PORTS)
    print(f'\n  Waiting for dashboards to start', end='', flush=True)
    while pending and time.time() < deadline:
        for name in list(pending):
            port = pending[name]
            try:
                urllib.request.urlopen(f'http://localhost:{port}/healthz', timeout=1)
                del pending[name]
            except Exception:
                pass
        if pending:
            print('.', end='', flush=True)
            time.sleep(1)
    print()
    if pending:
        print(f'  WARN  Still waiting on: {", ".join(pending)}')


def open_browser():
    master_url = f'http://localhost:{PORTS["Master Hub"]}'
    print(f'\n  Opening browser → {master_url}')
    time.sleep(1)
    webbrowser.open(master_url)


def main():
    parser = argparse.ArgumentParser(description='NSE Strategy Hub launcher')
    parser.add_argument('--dash-only', action='store_true',
                        help='Skip data update; launch dashboards only')
    parser.add_argument('--data-only', action='store_true',
                        help='Update data only; do not launch dashboards')
    args = parser.parse_args()

    print('\n' + sep('═'))
    print('  NSE STRATEGY HUB — Run All')
    print(sep('═'))

    # ── Step 1: Update data ────────────────────────────────────────────────────
    if not args.dash_only:
        print(f'\n{sep()}\n  STEP 1 — Update all strategy data\n{sep()}')
        all_ok = True
        for strategy, commands in PIPELINES.items():
            ok = run_pipeline(strategy, commands)
            if not ok:
                print(f'\n  WARNING: {strategy} pipeline failed — continuing with existing data.')
                all_ok = False
        if all_ok:
            print(f'\n  All pipelines completed successfully.')
        else:
            print(f'\n  Some pipelines had errors. Dashboards will show existing data.')

    # ── Step 2: Launch dashboards ──────────────────────────────────────────────
    if not args.data_only:
        print(f'\n{sep()}\n  STEP 2 — Launch dashboards\n{sep()}\n')
        procs = launch_dashboards()
        wait_for_dashboards()
        open_browser()

        print(f'\n{sep("═")}')
        print('  All dashboards running. Press Ctrl+C to stop.\n')
        for name, port in PORTS.items():
            print(f'  {name:<22} http://localhost:{port}')
        print(sep('═') + '\n')

        try:
            while True:
                time.sleep(5)
                # Restart any crashed processes
                for proc in procs:
                    if proc.poll() is not None:
                        procs.remove(proc)
        except KeyboardInterrupt:
            print('\n  Shutting down dashboards…')
            for proc in procs:
                proc.terminate()
            print('  Done.\n')

    elif args.data_only:
        print(f'\n{sep("═")}')
        print('  Data update complete. Run without --data-only to launch dashboards.')
        print(sep('═') + '\n')


if __name__ == '__main__':
    main()
