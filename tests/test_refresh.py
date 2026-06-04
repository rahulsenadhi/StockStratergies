# tests/test_refresh.py
import datetime as dt
import pandas as pd
import pytest
from core import refresh


def _seed(folder):
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "Date": ["2024-05-30"], "Open": 1.0, "High": 1.0, "Low": 1.0,
        "Close": 1.0, "Volume": 1,
    }).to_csv(folder / "AAA.csv", index=False)


def test_refresh_strategy_runs_fetch_sync_precompute(tmp_path, monkeypatch):
    folder = tmp_path / "ds"
    _seed(folder)

    monkeypatch.setitem(refresh.STRATEGY_CFG, "test", {
        "folder": str(folder),
        "dataset": "test_ds",
        "tickers_fn": lambda: ["AAA"],
        "precompute": ["fake_precompute.py"],
    })

    fetched = {}
    def fake_refresh_tickers(tickers, data_folder, today, fetch_fn, **kw):
        fetched["tickers"] = list(tickers)
        return {"AAA": "gap_appended(2)"}
    monkeypatch.setattr(refresh.incremental, "refresh_tickers", fake_refresh_tickers)

    ran = []
    def fake_run(cmd, **kw):
        ran.append(cmd)
        class R:  # minimal CompletedProcess stand-in
            returncode = 0
        return R()
    monkeypatch.setattr(refresh.subprocess, "run", fake_run)

    status = refresh.refresh_strategy("test")

    assert fetched["tickers"] == ["AAA"]
    assert status == {"AAA": "gap_appended(2)"}
    # one sync call + one precompute call
    assert any("convert_to_parquet.py" in " ".join(c) for c in ran)
    assert any("fake_precompute.py" in " ".join(c) for c in ran)


def test_refresh_strategy_unknown_name_raises():
    with pytest.raises(KeyError):
        refresh.refresh_strategy("does-not-exist")


def test_refresh_strategy_all_failed_raises(tmp_path, monkeypatch):
    folder = tmp_path / "ds"
    _seed(folder)
    monkeypatch.setitem(refresh.STRATEGY_CFG, "test", {
        "folder": str(folder), "dataset": "test_ds",
        "tickers_fn": lambda: ["AAA"], "precompute": [],
    })
    monkeypatch.setattr(refresh.incremental, "refresh_tickers",
                        lambda *a, **k: {"AAA": "failed(Timeout)"})
    ran = []
    monkeypatch.setattr(refresh.subprocess, "run",
                        lambda cmd, **k: ran.append(cmd))
    with pytest.raises(RuntimeError):
        refresh.refresh_strategy("test")
    assert ran == []          # no sync/precompute after all-failed


def test_refresh_strategy_script_mode_runs_script_only(monkeypatch):
    monkeypatch.setitem(refresh.STRATEGY_CFG, "scripted", {
        "folder": "data", "dataset": None, "script": "step1_download_data.py",
    })
    called = []
    monkeypatch.setattr(refresh.subprocess, "run",
                        lambda cmd, **k: called.append(cmd))
    # incremental must NOT be invoked in script mode
    monkeypatch.setattr(refresh.incremental, "refresh_tickers",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not fetch")))
    result = refresh.refresh_strategy("scripted")
    assert result == {}
    assert len(called) == 1
    assert "step1_download_data.py" in " ".join(called[0])


def test_refresh_strategy_no_dataset_skips_sync(tmp_path, monkeypatch):
    folder = tmp_path / "ds"
    _seed(folder)
    monkeypatch.setitem(refresh.STRATEGY_CFG, "test", {
        "folder": str(folder), "dataset": None,        # no parquet store
        "tickers_fn": lambda: ["AAA"], "precompute": [],
    })
    monkeypatch.setattr(refresh.incremental, "refresh_tickers",
                        lambda *a, **k: {"AAA": "gap_appended(1)"})
    ran = []
    monkeypatch.setattr(refresh.subprocess, "run",
                        lambda cmd, **k: ran.append(cmd))
    refresh.refresh_strategy("test")
    assert ran == []          # dataset None -> no convert_to_parquet call
