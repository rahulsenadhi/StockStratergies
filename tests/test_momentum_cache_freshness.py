"""The live Momentum scanner must not trust a per-ticker indicator cache older than its CSV."""
import numpy as np
import pandas as pd

from tests.test_modern_table import md  # master_dashboard loaded with a fake streamlit

N_BARS = 700
STALE_BARS = 85  # about 120 calendar days
LAST_DATE = '2026-11-06'


def _prices() -> pd.DataFrame:
    """A smooth uptrend, a sharp dip below the EMA220 ~66 bars ago, then recovery: a Watch Zone."""
    x = np.arange(N_BARS)
    p = np.interp(x, [0, 300, N_BARS - 74, N_BARS - 66, N_BARS - 59, N_BARS - 1],
                  [109.69, 127.54, 163.36, 128.06, 155.2, 163.23])
    idx = pd.bdate_range(end=LAST_DATE, periods=N_BARS)
    return pd.DataFrame({'Open': p, 'High': p * 1.003, 'Low': p * 0.997, 'Close': p,
                         'Volume': np.full(N_BARS, 5e5)}, index=idx)


def _indicators(df: pd.DataFrame) -> pd.DataFrame:
    c, v = df['Close'], df['Volume']
    ema220 = c.ewm(span=220, adjust=False).mean()
    high52 = c.rolling(252).max()
    ath = c.expanding().max()
    chop = md._compute_choppiness(df, 14)
    return pd.DataFrame({
        'open': df['Open'], 'close': c, 'volume': v,
        'sma50': c.rolling(50).mean(), 'sma150': c.rolling(150).mean(), 'ema220': ema220,
        'high52w': high52, 'low52w': c.rolling(252).min(), 'ath': ath,
        'close_s': c.shift(1), 'vol_avg50_s': v.rolling(50).mean().shift(1),
        'had_ema_dip_s': (c < ema220).astype(int).rolling(90).max().astype(bool).shift(1, fill_value=False),
        'choppiness_s': chop.shift(1), 'momentum_6m_s': c.pct_change(126).shift(1),
        'ath_prev': ath.shift(1), 'high52w_s': high52.shift(1),
    })


def _write_csv(folder, name, df):
    out = df.copy()
    out.index.name = 'Date'
    out.to_csv(folder / f'{name}.csv')


def _build(tmp_path, monkeypatch):
    csv_dir = tmp_path / 'data' / 'nse_bse'
    cache_dir = tmp_path / 'data' / 'indicator_cache'
    csv_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)
    full = _prices()
    stale_cache_end = full.iloc[:-STALE_BARS]
    _write_csv(csv_dir, 'AAA.NS', full)
    _write_csv(csv_dir, 'ZZZ.NS', full)
    _indicators(full).to_parquet(cache_dir / 'AAA.NS.parquet')
    _indicators(stale_cache_end).to_parquet(cache_dir / 'ZZZ.NS.parquet')
    monkeypatch.setattr(md, 'BASE_DIR', str(tmp_path))
    return full, stale_cache_end


def test_stale_cache_ticker_is_recomputed_from_csv(tmp_path, monkeypatch):
    full, old = _build(tmp_path, monkeypatch)
    sigs, funnel = md._compute_momentum_signals()

    rows = sigs.set_index('Ticker')
    assert funnel['stale_cache'] == 1
    assert {'AAA', 'ZZZ'} <= set(rows.index)
    assert rows.loc['ZZZ', 'Close'] == round(float(full['Close'].iloc[-1]), 2)
    assert rows.loc['ZZZ', 'Close'] != round(float(old['Close'].iloc[-1]), 2)
    assert rows.loc['ZZZ', 'Data as of'] == LAST_DATE


def test_fresh_cache_ticker_keeps_fast_path_and_reports_bar_date(tmp_path, monkeypatch):
    _build(tmp_path, monkeypatch)
    sigs, _ = md._compute_momentum_signals()
    assert sigs.set_index('Ticker').loc['AAA', 'Data as of'] == LAST_DATE


def test_every_signal_row_carries_data_as_of(tmp_path, monkeypatch):
    _build(tmp_path, monkeypatch)
    sigs, funnel = md._compute_momentum_signals()
    assert sigs['Data as of'].notna().all()
    assert funnel['final'] == len(sigs)
