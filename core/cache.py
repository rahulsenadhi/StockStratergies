"""Parquet indicator cache.

Generalizes the Momentum Edge per-ticker parquet cache so all three strategies
can share `data/indicator_cache/<strategy>/<ticker>.parquet`.

Cache key = MD5 of:
  • selected CFG values (caller supplies key list)
  • source CSV mtime

If either changes, the parquet is treated as stale.

API:
    key = cfg_hash(cfg, key_fields)
    df = load(strategy, ticker, expected_key, expected_mtime)   # None if stale
    save(strategy, ticker, df, key, mtime)
    clear(strategy=None)                                         # wipe sub-tree or all
"""

import hashlib
import shutil
from pathlib import Path

import pandas as pd

CACHE_ROOT = Path('data/indicator_cache')
_META_KEY = 'cache_key'
_META_MTIME = 'src_mtime'


def cfg_hash(cfg: dict, key_fields: list[str]) -> str:
    """Stable 12-char MD5 hash of selected cfg fields. Order-independent."""
    parts = [f'{k}={cfg.get(k)}' for k in sorted(key_fields)]
    blob = '|'.join(parts)
    return hashlib.md5(blob.encode()).hexdigest()[:12]


def _path(strategy: str, ticker: str) -> Path:
    safe = ticker.replace('/', '_').replace('\\', '_')
    return CACHE_ROOT / strategy / f'{safe}.parquet'


def load(
    strategy: str,
    ticker: str,
    expected_key: str,
    expected_mtime: float,
) -> pd.DataFrame | None:
    """Return cached DataFrame if key+mtime match; else None."""
    p = _path(strategy, ticker)
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
        meta = df.attrs
        if meta.get(_META_KEY) != expected_key:
            return None
        if abs(float(meta.get(_META_MTIME, 0.0)) - expected_mtime) > 1e-6:
            return None
        return df
    except Exception:
        return None


def save(strategy: str, ticker: str, df: pd.DataFrame, key: str, mtime: float) -> None:
    """Write parquet with embedded cache key + mtime metadata."""
    p = _path(strategy, ticker)
    p.parent.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    df.attrs[_META_KEY] = key
    df.attrs[_META_MTIME] = float(mtime)
    try:
        df.to_parquet(p, index=True)
    except Exception:
        pass


def clear(strategy: str | None = None) -> int:
    """Delete cache files. Returns count of files removed.

    strategy=None wipes the whole indicator_cache tree.
    """
    target = CACHE_ROOT / strategy if strategy else CACHE_ROOT
    if not target.exists():
        return 0
    count = sum(1 for _ in target.rglob('*.parquet'))
    shutil.rmtree(target, ignore_errors=True)
    return count
