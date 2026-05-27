# AP-Lite Diagnose-Modus — V1 (Plan)

**Stand:** 27.05.2026 Nachmittag, Mike-Spec ausgearbeitet im Dialog.
**Workflow:** V1 → V2 (Self-Review) → R1 (DeepSeek) → V3 → Code → Final-R1.
**Trivial-Klausel:** NEIN — Settings-Migration + Algo-Verhalten-Erweiterung
+ Logging-Framework-Integration. Voller Workflow Pflicht.

## 1. Mike's Problem

AP-Lite ist seit v0.97.90 (22.05.2026) produktiv (Option D — A-Priori-
Kandidaten-Matching, beratend). Mike's `~/.simpleft8/ap_lite_stats.json`
zeigt seitdem `rescue_count: 0` — **kein einziger Treffer in 5 Tagen**.

Wir wissen nicht warum:
- Wird AP-Lite überhaupt aufgerufen? (4 Guards in `_run_ap_lite_rescue`)
- Scheitert es am Margen-Threshold (heute MARGIN_MIN=0.05)?
- Liefert es bei dekodierten Partnern überhaupt sinnvolle Scores?

**Ohne Daten ist jede „Algo-Tuning"-Entscheidung Stochern.** Mike-Wort
27.05.: „die log ist ja für dich so das wir mal sehen können was wirklich
passiert … ich habe keine idee".

## 2. Mike-Spec (im Dialog erarbeitet)

**Kernidee:** AP-Lite parallel zum Decoder laufen lassen (Test-Modus), damit
wir Performance an dekodierten Partnern messen können — bei starken Signalen
wissen wir die Wahrheit (Decoder dekodiert „DA1MHH XYZ R-15") und können
gegenchecken ob AP-Lite das gleiche sieht.

**Plan stufenweise:**
1. **Algo zum Laufen bringen** — Test-Modus + Logging + Settings-Justage
2. **Daten sammeln** — 1-2 Sessions mit Debug-Log AN, Test-Modus AN
3. **Auswerten** — Algo funktional? Margen-Statistik? SNR-Korrelation?
4. **Schwelle iterativ ins Negative schieben** — wenn der Algo bei -10 dB
   stabil 80%+ trifft, runter auf -15, dann -20, …
5. **Optional UI-Polish** — Mike-Wort 27.05.: „mich juckt erstmal gar nicht
   was ich sehen kann, die log datei sehen das ist viel wichtiger"

## 3. Settings-Erweiterung (4 neue Keys)

| Key | Type | Default | Range/Werte | Bedeutung |
|---|---|---|---|---|
| `ap_lite_enabled` | bool | `True` | — | Master-Toggle. Ersetzt hartkodierte `AP_LITE_ENABLED` Konstante in `core/ap_lite.py:42`. |
| `ap_lite_test_mode` | bool | `False` | — | Wenn `True`: AP-Lite läuft ZUSÄTZLICH bei bereits dekodierten Partnern (Algo-Test gegen Decoder-Wahrheit). KEINE Info-Zeile im QSO-Panel im Test-Modus (sonst Doppel-Anzeige). |
| `ap_lite_min_snr_db` | int | `-20` | -25 bis -5 | AP-Lite versucht Rettung nur wenn `last_snr ≤ Schwelle`. Im Test-Modus IGNORIERT (Test-Modus läuft bei jedem Signal). |
| `ap_lite_strictness` | str | `"normal"` | `"locker"`/`"normal"`/`"streng"` | Margen-Mapping: locker=0.03 / normal=0.05 (heute) / streng=0.10. |

**Settings-Migration:** keine. Bei Frischstart Default-Werte. Alte
Configs ohne diese Keys → `dict.update()` lädt nur vorhandene Keys,
neue erscheinen automatisch.

**Strenge-Mapping als Modul-Konstante in `core/ap_lite.py`:**
```python
STRICTNESS_MARGIN_MAP = {
    "locker": 0.03,
    "normal": 0.05,
    "streng": 0.10,
}
def _resolve_margin(strictness: str) -> float:
    return STRICTNESS_MARGIN_MAP.get(strictness, STRICTNESS_MARGIN_MAP["normal"])
```

## 4. Code-Änderungen

### 4.1 `config/settings.py` — DEFAULTS erweitern

```python
DEFAULTS = {
    ...,
    # AP-Lite Diagnose-Modus (2026-05-27):
    "ap_lite_enabled": True,
    "ap_lite_test_mode": False,
    "ap_lite_min_snr_db": -20,
    "ap_lite_strictness": "normal",
}
```

### 4.2 `core/ap_lite.py` — Konstanten dynamisch + Logging

**Änderungen:**
- `AP_LITE_ENABLED: bool = True` BLEIBT als Fallback (für Standalone-Tests
  ohne Settings-Objekt).
- `MARGIN_MIN: float = 0.05` BLEIBT als Default-Fallback.
- Neue Klassenattribute in `APLite.__init__`:
  ```python
  def __init__(self, encoder=None, stats_path: Optional[str] = _STATS_PATH):
      self.enabled = AP_LITE_ENABLED          # Settings überschreibt später
      self.test_mode = False                  # Settings überschreibt später
      self.min_snr_db = -20                   # Settings überschreibt später
      self.margin_min = MARGIN_MIN            # Settings überschreibt später
      ...
  ```
- Neue Methode `apply_settings(settings)`:
  ```python
  def apply_settings(self, settings) -> None:
      """Aus Settings-Objekt nachladen. Idempotent."""
      self.enabled = bool(settings.get("ap_lite_enabled", True))
      self.test_mode = bool(settings.get("ap_lite_test_mode", False))
      self.min_snr_db = int(settings.get("ap_lite_min_snr_db", -20))
      strict = str(settings.get("ap_lite_strictness", "normal"))
      self.margin_min = _resolve_margin(strict)
  ```
- `try_rescue` neuer optionaler Parameter `decoder_said: Optional[str] = None`
  (im Test-Modus übergeben — Klartext-Vergleich im Log).
- `try_rescue` nutzt `self.margin_min` statt globaler `MARGIN_MIN`.
- Debug-Log-Calls (via `core.debug_log.debug_log("AP-LITE", ...)`):

| Punkt | Log-Eintrag |
|---|---|
| try_rescue Entry | `CALL state={s} call={c} freq_hz={f:.0f} snr_est={n} test_mode={t}` |
| Skip „enabled=False" | `SKIP reason=disabled` |
| Skip „bad args" | `SKIP reason=bad_args call='{c}' state={s}` |
| Skip „no pcm" | `SKIP reason=no_pcm` |
| Skip „too few candidates" | `SKIP reason=few_cands n={n} (state {s} → 0/zu wenig)` |
| Nach Scoring (immer) | `SCORED n_cands={n} best={b:.3f} runner={r:.3f} margin={m:.3f} threshold={t:.3f} best_cand='{c}'` |
| MATCH | `MATCH cand='{c}' score={s:.3f} margin={m:.3f} total_rescues={n}` |
| NO_MATCH | `NO_MATCH best={b:.3f} margin={m:.3f} threshold={t:.3f}` |
| Test-Modus Vergleich | `TEST_COMPARE decoder='{d}' aplite='{a}' agreement={Y/N} margin={m:.3f}` |

### 4.3 `ui/mw_cycle.py:493 _run_ap_lite_rescue` — Test-Modus + Guard-Logging

Änderungen:
- Vor jedem Skip-Pfad ein `debug_log("AP-LITE", "GUARD_SKIP reason=...")`.
- Im Test-Modus: `_partner_found`-Skip entfällt; AP-Lite läuft AUCH wenn
  Partner dekodiert ist; Decoder-Wahrheit wird als `decoder_said` übergeben.
- SNR-Filter (außerhalb Test-Modus): `if last_snr > min_snr_db: skip`.
- Im Test-Modus KEIN `qso_panel.add_info` aufrufen (Mike-Spec): nur
  Debug-Log enthält den Vergleich.

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
    _partner_msg = next((m for m in (messages or [])
                          if getattr(m, 'caller', '') == _their), None)
    _partner_found = _partner_msg is not None
    if _partner_found and not self._ap_lite.test_mode:
        _dbg("AP-LITE", f"GUARD_SKIP reason=partner_decoded call={_their}")
        return
    if self.decoder.last_pcm_12k is None:
        _dbg("AP-LITE", "GUARD_SKIP reason=no_pcm")
        return
    _last_snr = float(getattr(self.qso_sm, '_last_snr', -10))
    if not self._ap_lite.test_mode and _last_snr > self._ap_lite.min_snr_db:
        _dbg("AP-LITE", f"GUARD_SKIP reason=snr_too_strong "
                        f"last_snr={_last_snr:.0f} threshold={self._ap_lite.min_snr_db}")
        return
    _freq = float(getattr(self.qso_sm.qso, 'freq_hz',
                          self.encoder.audio_freq_hz) or self.encoder.audio_freq_hz)
    _qso_state_int = 1 if _state == QSOState.WAIT_REPORT else 2
    _decoder_said = _partner_msg.text if _partner_msg else None
    _result = self._ap_lite.try_rescue(
        self.decoder.last_pcm_12k, _freq, _their, _qso_state_int,
        own_callsign=self.settings.callsign,
        own_locator=self.settings.locator,
        snr_estimate=_last_snr,
        decoder_said=_decoder_said,
    )
    if _result and _result.success:
        # Im Test-Modus KEINE Info-Zeile — nur Log (Mike-Spec)
        if not self._ap_lite.test_mode:
            self.qso_panel.add_info(
                f"[AP-Lite] Erkannt: {_result.recovered_message} "
                f"(Marge {_result.margin:.2f})"
            )
```

### 4.4 `main_window.py` (oder wo `APLite` instanziiert wird) — Settings binden

In `__init__` nach Instanziierung: `self._ap_lite.apply_settings(self.settings)`.
Plus Hook bei Settings-Dialog-OK: nach Save erneut aufrufen damit Live-Änderungen
greifen ohne App-Neustart.

### 4.5 UI — Settings-Dialog erweitern

Mike-Spec 27.05.: „mich juckt erstmal gar nicht was ich sehen kann".
**Phase 1 (jetzt):** UI ist Pflicht weil sonst Mike nichts ändern kann
(hartkodieren wäre Workflow-Verletzung). KISS-Variante:

Neuer GroupBox „AP-Lite (Diagnose)" im Tab „Erweitert" (oder neuer Tab
„Diagnose"). 4 Widgets:
```
☐ AP-Lite aktivieren                              [ap_lite_enabled]
☐ Test-Modus (auch bei dekodiertem Partner)       [ap_lite_test_mode]
   Tooltip: „Nur Diagnose. Loggt Algo gegen Decoder-Wahrheit."
AP-Lite greift bei Partner-SNR ≤ [-20] dB         [ap_lite_min_snr_db, QSpinBox]
   Range -25 bis -5, suffix " dB"
Strenge:                          [normal ▾]       [ap_lite_strictness, QComboBox]
   Items: locker / normal / streng
```

Speichern: in `_on_save`-Slot (oder analog) `settings.set(...)` für jeden
Key, dann `settings.save()`, dann `main_window._ap_lite.apply_settings(settings)`
triggern.

## 5. Tests (zu schreiben)

| Datei | Coverage |
|---|---|
| `tests/test_ap_lite_diagnose_settings.py` | T1: Default-Werte aus DEFAULTS. T2: `apply_settings` lädt korrekt. T3: Strenge-Mapping locker/normal/streng. T4: Unbekannter Strenge-Wert → Fallback „normal". |
| `tests/test_ap_lite_diagnose_logging.py` | T5: Debug-Log AUS = keine Calls. T6: Debug-Log AN = Calls landen. T7: try_rescue logs alle Skip-Reasons. T8: SCORED enthält n_cands/best/runner/margin. T9: MATCH enthält total_rescues. T10: TEST_COMPARE enthält decoder_said + agreement. |
| `tests/test_ap_lite_diagnose_test_mode.py` | T11: test_mode=True umgeht partner_decoded-Guard. T12: test_mode=True umgeht snr_filter-Guard. T13: test_mode=True ruft KEINE qso_panel.add_info. T14: test_mode=False weiterhin alle Guards aktiv. |
| `tests/test_ap_lite_diagnose_snr_filter.py` | T15: last_snr > min_snr_db → Skip. T16: last_snr == min_snr_db → run. T17: last_snr < min_snr_db → run. T18: SNR-Filter im test_mode ignoriert. |

Erwartet: **18 neue Tests**, 2167 → 2167+18 = 2185 grün.

## 6. Risiken & Trade-offs

| Risiko | Severity | Mitigation |
|---|---|---|
| Test-Modus erzeugt CPU-Load (Korrelations-Versuche bei jedem dekodierten Partner) | 🟡 | Korrelation läuft auf 30s-PCM-Slot, FFT-basiert. Bei 1 QSO/Slot eher unkritisch. Falls Performance-Problem: nur in WAIT_REPORT/WAIT_RR73 = sowieso eingeschränkt. |
| Debug-Log-Spam (Test-Modus + viele dekodierte Partner = viele Zeilen) | 🟡 | Mike entscheidet wann er Debug-Log AN macht. Standard AUS = Zero-Cost. Log-Dateien werden nach 1 Tag rotiert (Cleanup-Mechanismus existiert). |
| Settings-Migration vergessen | 🟠 | `DEFAULTS` Erweiterung greift bei Frischstart UND beim `_data.update()` in `load()` — alte Configs bekommen die Defaults via Initial-`dict(DEFAULTS)`. T1 verifiziert das. |
| `apply_settings` nach Settings-Dialog-Save vergessen | 🟠 | T-Plan: explizit testen + main_window-Hook absichern. |
| `decoder_said` Parameter ist optional → bestehende Tests brechen evtl. nicht — aber Code-Pfade müssen `decoder_said=None` defensive handhaben | 🟢 | Default-Param in try_rescue Signatur. Unit-Test für decoder_said=None. |
| Strenge-Mapping-Konstanten driften zwischen Settings-Dialog (Strings) und Modul-Konstante (Floats) | 🟡 | Single Source of Truth: `STRICTNESS_MARGIN_MAP` in ap_lite.py, ComboBox-Items aus dessen Keys generiert (oder hartkodiert mit Kommentar „muss sync sein"). |

## 7. Nicht-Ziele (jetzt nicht bauen)

- KEINE UI-Anzeige der AP-Lite-Treffer-Statistik (Counter im Dashboard etc.) — kommt nach erfolgreichem Diagnose-Lauf.
- KEINE automatische Margen-Tuning-Heuristik. Mike entscheidet manuell aufgrund Log-Daten.
- KEINE Persistierung des Test-Modus über Sessions (Default = OFF, Mike aktiviert bewusst).
- KEINE Erweiterung der Kandidaten-Generator-Logik. Algo bleibt Option-D-Stand v0.97.90.
- KEINE Änderung an `correlate_candidate`. Pure Diagnose, kein Algo-Refactor.

## 8. Reihenfolge der Commits (atomar)

1. **C1:** `config/settings.py` DEFAULTS erweitern + Tests T1.
2. **C2:** `core/ap_lite.py` `apply_settings` + STRICTNESS_MARGIN_MAP + Tests T2-T4.
3. **C3:** `core/ap_lite.py` `try_rescue` Debug-Log + `decoder_said` + Tests T5-T9.
4. **C4:** `ui/mw_cycle.py` Test-Modus + Guard-Logs + SNR-Filter + Tests T10-T18.
5. **C5:** `ui/settings_dialog.py` GroupBox + Save-Hook + manueller Smoke-Test.
6. **C6:** APP_VERSION + HISTORY + HANDOFF + CLAUDE.md Header + Memory.

## 9. Offen — V2 Self-Review klären

- `settings.get_callsign()`-API vs. direkt `settings.callsign` — was nutzt die heutige `mw_cycle.py`?
- Wo wird `APLite` instanziiert? `main_window.py` oder `mw_cycle.__init__`?
- Hat `settings_dialog.py` schon einen Tab „Erweitert" oder müssen wir einen neuen anlegen?
- Wird `apply_settings` beim **App-Start** automatisch nach `Settings.load()` aufgerufen oder nur bei Dialog-Save?
- ComboBox-Items: Strings „locker"/„normal"/„streng" persistieren oder Ints 0/1/2 mit Mapping?

## 10. V2 Self-Review (27.05.2026 nachmittag)

### Klärungen zu §9 (Code-Verifikation gemacht)

| Frage | Antwort |
|---|---|
| `settings.callsign`? | **Attribute-Access** wie `band`/`mode`. `mw_cycle.py:516` macht `self.settings.callsign`. Pattern beibehalten. |
| Wo wird APLite instanziiert? | `ui/main_window.py:416` via `ap_lite.get_instance(encoder=self.encoder)` — Singleton-Pattern. `apply_settings()` Aufruf gehört direkt nach Instanziierung. |
| Welcher Settings-Tab? | Es gibt KEINEN „Erweitert"-Tab. Tabs: Station / TX & Schutz / FT8 & Diversity / Daten & Tools. **Wahl: „Daten & Tools"** (Diagnose-Charakter passt am besten). |
| Wann `apply_settings`? | (a) Einmal in `main_window.__init__` nach `get_instance()`. (b) Nach `SettingsDialog.exec()` mit Accepted-Return (vorhandener Save-Pfad in `main_window`). Idempotent — Aufruf-Reihenfolge egal. |
| ComboBox-Items? | **Strings** persistieren („locker"/„normal"/„streng"). Selbsterklärend in JSON, kein Int-Mapping nötig. Defensive bei Unbekanntem → Fallback „normal". |

### Findings

**V2-F1 🟠 (Bug-Fund):** Mein V1 §4.2 packte den Test-Modus-Vergleich
(`TEST_COMPARE decoder='X' aplite='Y'`) IN `try_rescue`. Aber `try_rescue`
kennt `decoder_said` nicht ohne neuen Parameter — und der Vergleich
ist Caller-Wissen (in `mw_cycle.py` haben wir `_partner_msg.text`).
**V3-Korrektur:** `TEST_COMPARE` wird in `mw_cycle._run_ap_lite_rescue`
NACH `try_rescue` geloggt, nicht innerhalb. Der `decoder_said`-Parameter
in `try_rescue` ist überflüssig — entfernen.

**V2-F2 🟠 (Inkonsistenz):** Strenge-Mapping-Werte stehen im Plan zweimal
unterschiedlich: §3 Tabelle „locker=0.04/normal=0.08/streng=0.12", §4.2
Code „locker=0.03/normal=0.05/streng=0.10". **Korrekte Werte:** locker=0.03
/ **normal=0.05 (heutiger MARGIN_MIN!)** / streng=0.10. V1 §3 falsch
zitiert — Quelle ist `core/ap_lite.py:50` mit `MARGIN_MIN = 0.05`.

**V2-F3 🟠 (Ticket-Nummer fehlt):** Das ist **P149** (nach P148 SWR-Anzeige).
Naming-Konsistenz wichtig für HISTORY/Memory/Commit-Messages.

**V2-F4 🟡:** APP_VERSION 0.98.29 → 0.98.30 (Feature-Add: 4 neue Settings,
Test-Modus, Diagnose-Logging, UI-Erweiterung. Patch-Bump nicht ausreichend.)

**V2-F5 🟡 (Performance):** FFT auf 30s @ 12 kHz = 360 k Samples,
~50-200ms je Korrelation. Bei 5-15 Kandidaten = 0.5-3s pro Slot.
Test-Modus läuft NUR bei aktivem QSO in WAIT_REPORT/WAIT_RR73 mit erwartetem
Partner = max 1 try_rescue/Slot. Slot=15s → unkritisch. Keine Mitigation
nötig.

**V2-F6 🟡 (Frequenz-Quelle im Test-Modus):** V1 §4.3 nutzt
`qso_sm.qso.freq_hz` als primäre Quelle. Aber im Test-Modus mit dekodiertem
Partner haben wir die ECHTE Frequenz in `_partner_msg.audio_freq_hz`.
**V3-Verbesserung:** im Test-Modus `_partner_msg.audio_freq_hz`
bevorzugen (präziser für Korrelation, kein ±5 Hz-Suchaufwand nötig).

**V2-F7 🟡 (Test-File-Aufteilung):** V1 §5 listet 4 separate Test-Dateien.
KISS: alles in einer Datei `tests/test_p149_ap_lite_diagnose.py` mit 18
Tests in Gruppen (Settings/Logging/TestMode/SNR-Filter). Pattern wie P139.

**V2-F8 🟠 (apply_settings Race):** Wenn Mike Settings ändert während
ein Slot läuft, sieht der laufende Slot evtl. noch alte Werte. Akzeptabel
(sub-15s Verzögerung) — aber im Plan explizit dokumentieren: „Live-
Änderungen greifen ab nächstem Slot". KEINE Lock-Mechanik bauen.

**V2-F9 🟡 (Settings-Dialog Save-Hook):** Wo genau ruft `main_window` nach
Dialog-OK `_ap_lite.apply_settings(self.settings)` auf? Code-Pfad muss
recherchiert werden — vermutlich in `main_window._open_settings()`-Slot
nach `if dlg.exec() == QDialog.Accepted: self.settings.save(); ...`.

**V2-F10 🟢 (Counter-Verhalten):** Im Test-Modus mit Decoder-Erfolg läuft
`self.attempt_count += 1` (Z. 294 in ap_lite.py) bei jedem Versuch. Counter
wächst schneller im Test-Modus — das ist gewollt (Mike sieht im Log
„Anzahl Versuche" als Indikator). `rescue_count` (persistent) zählt
weiterhin nur echte Treffer (margin ≥ threshold). KISS.

**V2-F11 🟢 (Default-Werte):** `min_snr_db=-20` ist Mike's gewünschter
Startpunkt. Range -25 bis -5 gibt genug Spielraum. `strictness="normal"`
= heutiges Verhalten (rückwärtskompatibel ohne Test-Modus).

**V2-F12 🟢 (Doku):** FEATURES.md sollte einen neuen §13 NEU bekommen
„AP-Lite Diagnose-Modus" mit Erklärung der 4 Settings + Log-Format.
Aber erst NACH Field-Daten (sonst Doku der Hypothese, nicht der Realität).
Für V3 nur HISTORY-Eintrag, FEATURES später.

**V2-F13 🟡 (Ungenutzter `MARGIN_MIN` Import):** Nach Refactor in §4.2 bleibt
`MARGIN_MIN = 0.05` als Modul-Konstante erhalten (für Fallback). Tests die
`MARGIN_MIN` direkt importieren werden nicht brechen. Keine Migration nötig.

### V2-Ergebnis: ready für R1

V2-F1 + V2-F2 sind echte Bug-Fänge (Logging-Ort falsch, Mapping-Werte
inkonsistent). V2-F6 ist eine Algo-Verbesserung. Alles in V3 einbauen.
Ticket-Nummer P149 setzen.
