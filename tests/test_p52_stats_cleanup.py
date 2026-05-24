"""P52 (v0.97.41) — Stats-Toggle-Migration (Settings-Pop) — Rest-Tests.

Ursprünglich auch 90-Tage-Datum-Cleanup-Tests — diese wurden mit P116
(v0.98.01) durch FIFO-Sliding-Window ersetzt. Coverage für Bucket-Pruning
liegt jetzt in `test_p116_fifo_cleanup.py`. Hier nur noch die
Settings-Migration (T7), die nichts mit Stats-Cleanup zu tun hat, aber
historisch zum P52-Bundle gehört.
"""

from __future__ import annotations

import json
from pathlib import Path


# ── T7 — Settings-Migration: stats_enabled wird gepoppt ─────────────────


def test_t7_settings_migration_pops_stats_enabled(tmp_path, monkeypatch):
    """Alter Config-Key `stats_enabled` wird beim Load idempotent gepoppt
    (analog P47 audio_freq_hz/max_decode_freq)."""
    fake_config = tmp_path / "config.json"
    fake_config.write_text(json.dumps({
        "band": "40m",
        "mode": "FT8",
        "stats_enabled": False,
    }))

    from config import settings as settings_module
    monkeypatch.setattr(settings_module, "CONFIG_FILE", fake_config)

    s = settings_module.Settings()
    assert "stats_enabled" not in s._data
    # 2026-05-23: band/mode werden auf DEFAULTS gezwungen, egal was im
    # Settings-File steht (Persistenz entfernt — immer 20m FT8 beim Start).
    assert s.get("band") == settings_module.DEFAULTS["band"] == "20m"
    assert s.get("mode") == settings_module.DEFAULTS["mode"] == "FT8"
