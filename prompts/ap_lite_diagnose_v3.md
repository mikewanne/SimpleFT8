# P149 — AP-Lite Diagnose-Modus — V3 (Final-Spec)

**Stand:** 27.05.2026 nachmittag, nach V1 + V2-Self-Review + R1 DeepSeek-V4-pro.
**R1-Verdikt:** „NACHBESSERUNG NÖTIG" (2× 🔴 + 2× 🟠).
**V3 baut alle R1-Findings ein.**

## R1-Korrekturen

### Fix C1 (R1-F3 🔴): Partner-SNR-Cache statt globaler `_last_snr`

**Problem:** `qso_sm._last_snr` wird bei JEDEM Decode aktualisiert — auch
von fremden Stationen. Im verpassten Partner-Slot enthält der Wert den
SNR irgendeines fremden Decodes. SNR-Filter würde AP-Lite fälschlich
deaktivieren — könnte Mike's `rescue_count: 0` sogar verursachen.

**Fix:** Neuer Cache in `core/qso_state.py` — `QSOData.partner_last_snr:
Optional[float] = None`. Update NUR bei `msg.caller == qso.their_call`
in `qso_sm.on_message_received` (eine zusätzliche Zeile am passenden
Punkt). Bei erstmaligem Verpassen (Cache=None) → SNR-Filter SKIPT NICHT.

**SNR-Filter-Logik in `mw_cycle._run_ap_lite_rescue`:**
```python
if not self._ap_lite.test_mode:
    _psnr = self.qso_sm.qso.partner_last_snr  # Optional[float]
    if _psnr is not None and _psnr > self._ap_lite.min_snr_db:
        debug_log("AP-LITE",
            f"GUARD_SKIP reason=partner_snr_too_strong "
            f"partner_snr={_psnr:.0f} threshold={self._ap_lite.min_snr_db}")
        return
    # _psnr=None oder _psnr<=threshold → durchlaufen
```

### Fix C2 (R1-F7 🔴): `rescue_count` im Test-Modus nicht inkrementieren

**Problem:** Heute zählt `rescue_count` jeden margin-Treffer atomar +
persistiert. Im Test-Modus mit `_partner_found=True` würde der Counter
inflationär wachsen ohne Aussage.

**Fix:** Neuer Param `count_rescue: bool = True` in `try_rescue`. In
`mw_cycle._run_ap_lite_rescue` übergeben: `count_rescue=not test_mode`.

```python
def try_rescue(self, ..., count_rescue: bool = True) -> Optional[APLiteResult]:
    ...
    if margin >= self.margin_min:
        if count_rescue:
            self.rescue_count += 1
            self._save_rescue_count()
        logger.info(f"[AP-Lite] MATCH ...")
        return APLiteResult(success=True, ...)
```

### Fix C3 (R1-F4 🟠): Strenge-Mapping konservativ + Begründungs-Kommentar

```python
# 27.05.2026 (P149): empirisch noch nicht bestätigt — Werte basieren auf
# synthetischen Messungen v0.97.90 (echt ~0.11, Rauschen ≤0.023).
# Nach 1-2 Field-Sessions mit Test-Modus AN diese Werte überprüfen.
STRICTNESS_MARGIN_MAP = {
    "locker":  0.04,  # Sicherheitsabstand zum Rauschen 0.023
    "normal":  0.05,  # heutiger MARGIN_MIN — Verhalten unverändert bei Default
    "streng":  0.10,  # konservativ für klare Treffer
}
```

### Fix C4 (R1-F1 🟡): TEST_COMPARE-Log mit Transparenz-Hinweis

```python
debug_log("AP-LITE",
    f"TEST_COMPARE decoder='{decoder_said}' aplite='{aplite_said}' "
    f"agreement={'Y' if match else 'N'} margin={margin:.3f} "
    f"note='decoder=reference, not ground-truth'")
```

### Fix C5 (R1-F10 🟠 Edge-Case): Multiple Partner-Decodes

```python
_partner_msgs = [m for m in (messages or [])
                  if getattr(m, 'caller', '') == _their]
_partner_msg = _partner_msgs[0] if _partner_msgs else None  # erstes nehmen
_partner_found = bool(_partner_msgs)
# Edge-Case 2+ Decodes (Hash/Mumpitz): wir vergleichen nur das erste,
# das ist gut genug für die Diagnose-Phase.
```

## V3 — Konsolidierte Final-Spec

### Settings (4 neue Keys, V1-Stand)

```python
"ap_lite_enabled": True,
"ap_lite_test_mode": False,
"ap_lite_min_snr_db": -20,         # Range -25 bis -5 (UI-Spinbox)
"ap_lite_strictness": "normal",    # locker/normal/streng (UI-Combo)
```

### `core/qso_state.py` — Partner-SNR-Cache (R1-F3-Fix)

In `QSOData`-Dataclass:
```python
@dataclass
class QSOData:
    ...
    partner_last_snr: Optional[float] = None  # P149: SNR des letzten Decodes der Partner-Station
```

In `qso_sm.on_message_received` (oder wo `_last_snr` global gesetzt wird):
```python
# bestehender Code: self._last_snr = msg.snr (global)
# NEU dazu:
if self.qso and msg.caller == self.qso.their_call:
    self.qso.partner_last_snr = float(msg.snr)
```

### `core/ap_lite.py` — Settings-bindings + Param

```python
# Modul-Konstanten
STRICTNESS_MARGIN_MAP = { "locker": 0.04, "normal": 0.05, "streng": 0.10 }
def _resolve_margin(strictness: str) -> float:
    return STRICTNESS_MARGIN_MAP.get(strictness, STRICTNESS_MARGIN_MAP["normal"])

class APLite:
    def __init__(self, encoder=None, stats_path=_STATS_PATH):
        self.enabled = AP_LITE_ENABLED
        self.test_mode = False
        self.min_snr_db = -20
        self.margin_min = MARGIN_MIN
        self.encoder = encoder
        self._stats_path = stats_path
        self.attempt_count = 0
        self.rescue_count = self._load_rescue_count()

    def apply_settings(self, settings) -> None:
        """Aus Settings nachladen — idempotent."""
        self.enabled = bool(settings.get("ap_lite_enabled", True))
        self.test_mode = bool(settings.get("ap_lite_test_mode", False))
        self.min_snr_db = int(settings.get("ap_lite_min_snr_db", -20))
        strict = str(settings.get("ap_lite_strictness", "normal"))
        self.margin_min = _resolve_margin(strict)

    def try_rescue(self, ..., count_rescue: bool = True) -> Optional[APLiteResult]:
        # Bestehende Logik + neue Logs + count_rescue-Schalter
```

### `core/debug_log` — Aufrufe an strategischen Punkten

Beide Dateien (`ap_lite.py` + `mw_cycle.py`) bekommen
`from core.debug_log import debug_log` Import und strategische Calls
(Tabelle siehe V1 §4.2/§4.3, mit R1-F1-Update für TEST_COMPARE-Note
und neuer SNR-Filter-Log).

### `ui/mw_cycle.py:_run_ap_lite_rescue` — Test-Modus + Partner-SNR + Guards

Pseudo-Code:
```python
def _run_ap_lite_rescue(self, messages):
    from core.debug_log import debug_log as _dbg
    if not (self._ap_lite.enabled and self.qso_sm.qso):
        _dbg("AP-LITE", "GUARD_SKIP reason=no_qso_or_disabled")
        return
    _state = self.qso_sm.state
    if _state not in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73):
        _dbg("AP-LITE", f"GUARD_SKIP reason=wrong_state state={_state.name}")
        return
    _their = self.qso_sm.qso.their_call
    _partner_msgs = [m for m in (messages or [])
                      if getattr(m, 'caller', '') == _their]
    _partner_msg = _partner_msgs[0] if _partner_msgs else None
    _partner_found = bool(_partner_msgs)
    if _partner_found and not self._ap_lite.test_mode:
        _dbg("AP-LITE", f"GUARD_SKIP reason=partner_decoded call={_their}")
        return
    if self.decoder.last_pcm_12k is None:
        _dbg("AP-LITE", "GUARD_SKIP reason=no_pcm")
        return
    # R1-F3-Fix: SNR-Filter via partnergebundenem Cache
    if not self._ap_lite.test_mode:
        _psnr = self.qso_sm.qso.partner_last_snr  # Optional[float]
        if _psnr is not None and _psnr > self._ap_lite.min_snr_db:
            _dbg("AP-LITE",
                f"GUARD_SKIP reason=partner_snr_too_strong "
                f"partner_snr={_psnr:.0f} threshold={self._ap_lite.min_snr_db}")
            return
    # Frequenz-Quelle: Test-Modus = präzisere Partner-Msg-Frequenz
    if self._ap_lite.test_mode and _partner_msg is not None:
        _freq = float(getattr(_partner_msg, 'audio_freq_hz', 0))
    else:
        _freq = float(getattr(self.qso_sm.qso, 'freq_hz',
                              self.encoder.audio_freq_hz)
                      or self.encoder.audio_freq_hz)
    _qso_state_int = 1 if _state == QSOState.WAIT_REPORT else 2
    _snr_est = float(self.qso_sm.qso.partner_last_snr or -10)
    _result = self._ap_lite.try_rescue(
        self.decoder.last_pcm_12k, _freq, _their, _qso_state_int,
        own_callsign=self.settings.callsign,
        own_locator=self.settings.locator,
        snr_estimate=_snr_est,
        count_rescue=not self._ap_lite.test_mode,  # R1-F7-Fix
    )
    # Im Test-Modus: TEST_COMPARE-Log statt qso_panel.add_info
    if self._ap_lite.test_mode:
        _decoder_said = getattr(_partner_msg, 'text', None) if _partner_msg else None
        _aplite_said = _result.recovered_message if _result and _result.success else None
        _agreement = (_decoder_said is not None and _aplite_said is not None
                       and _aplite_said == _decoder_said)
        _margin = _result.margin if _result else 0.0
        _dbg("AP-LITE",
            f"TEST_COMPARE decoder='{_decoder_said}' aplite='{_aplite_said}' "
            f"agreement={'Y' if _agreement else 'N'} margin={_margin:.3f} "
            f"note='decoder=reference, not ground-truth'")
    # Im Produktiv-Modus (kein Test): Info-Zeile bei Match
    elif _result and _result.success:
        self.qso_panel.add_info(
            f"[AP-Lite] Erkannt: {_result.recovered_message} "
            f"(Marge {_result.margin:.2f})"
        )
```

### `ui/settings_dialog.py` — GroupBox in Tab „Daten & Tools"

KISS: 4 Widgets in 1 GroupBox. Save in vorhandenem Save-Slot.

### `ui/main_window.py` — `apply_settings`-Aufruf

(a) Nach `self._ap_lite = _ap.get_instance(...)` einmal `apply_settings(settings)`.
(b) Nach Settings-Dialog-Accepted ebenfalls (Hook im vorhandenen Open-Settings-Slot).

## Tests (R1-validiert)

Eine Datei `tests/test_p149_ap_lite_diagnose.py` mit ~22 Tests
(18 V1-Plan + 4 R1-Korrekturen):

| Gruppe | Tests |
|---|---|
| Settings (Defaults + Migration + Strenge-Mapping + apply_settings) | T1-T4 |
| Debug-Logging (alle Skip-Reasons + SCORED + MATCH + TEST_COMPARE) | T5-T11 |
| Test-Modus (Guard-Skips + KEINE add_info + count_rescue=False) | T12-T15 |
| Partner-SNR-Filter (R1-F3) | T16-T19 |
| count_rescue-Schalter (R1-F7) | T20 |
| Multiple-Partner-Edge-Case (R1-F10) | T21 |
| TEST_COMPARE-Note-Marker (R1-F1) | T22 |

Erwartet: 2149 → 2171 grün (+22).

## Reihenfolge der Commits

1. **C1:** `config/settings.py` DEFAULTS + `core/qso_state.py` partner_last_snr + Tests T1-T4 + T16-T19.
2. **C2:** `core/ap_lite.py` `apply_settings` + STRICTNESS_MARGIN_MAP + count_rescue + Tests T5-T11 + T20.
3. **C3:** `ui/mw_cycle.py` Test-Modus + Partner-SNR-Filter + Multiple-Partner-Edge + Tests T12-T15 + T21-T22.
4. **C4:** `ui/settings_dialog.py` GroupBox + Save-Hook + `ui/main_window.py` apply_settings-Aufrufe.
5. **C5:** APP_VERSION 0.98.29 → 0.98.30 + HISTORY + HANDOFF + CLAUDE.md Header + Memory.

## Final-Check vor Code-Phase

- [x] R1-🔴 F3 Partner-SNR-Cache eingebaut (C1)
- [x] R1-🔴 F7 count_rescue-Schalter eingebaut (C2)
- [x] R1-🟠 F4 Strenge-Werte konservativ (locker=0.04, R1-Empfehlung)
- [x] R1-🟠 F10 Multiple-Partner Edge-Case (defensives Listing)
- [x] R1-🟡 F1 TEST_COMPARE-Note „decoder=reference, not ground-truth"
- [x] R1-🟢 F2/F5/F6/F8/F9 unverändert (R1-OK)

**V3 Ready für Code.**
