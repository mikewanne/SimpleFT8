# P151 R1 — AP-Lite vollständig ausbauen — Review meiner Entfernungs-Liste

## Kontext

P150 (`kMin_score=4` für FT8) ist committed. Du hast vorhin selbst gesagt:
„AP-Lite verwerfen + Decoder-Bremse lösen — Option A + C, B keine Nische".

Jetzt P151: AP-Lite VOLLSTÄNDIG aus dem Code entfernen. Klar, sauber, kein
Halbschritt. Mike's Backup unter `Appsicherungen/2026-05-27_v0.98.31_vor_p150_p151/`
sichert Rollback falls je wiederbelebt.

## Entfernungs-Liste (V1)

### 6 Dateien KOMPLETT löschen

1. `core/ap_lite.py` (Hauptmodul, 407 LOC)
2. `tests/test_ap_lite.py`
3. `tests/test_ap_lite_e2e.py`
4. `tests/test_p149_ap_lite_diagnose.py`
5. `docs/explained/ap-lite.md`
6. `docs/explained/ap-lite_de.md`

### Code-Änderungen (Stellen entfernen)

| Datei | Zeilen | Was |
|---|---|---|
| `core/encoder.py` | 169-187 | Methode `generate_reference_wave` (nur AP-Lite + 1 Test der gelöscht wird) |
| `core/decoder.py` | 84 + 332 | `self.last_pcm_12k` init + update — Kommentar bestätigt „AP-Lite: letzter 12kHz float32 Buffer" |
| `core/qso_state.py` | 133 + 561 | `QSOData.partner_last_snr` field + update in `on_message_received` |
| `ui/main_window.py` | 418-420, 1271, 1374-1375 | Init `_ap_lite = ap_lite.get_instance(encoder=...)`, `apply_settings`-Aufruf nach Dialog-Save, Statusbar-Counter `AP = (X)` |
| `ui/mw_cycle.py` | 160 + 493-578 | Aufruf `_run_ap_lite_rescue(messages)` + Methode `_run_ap_lite_rescue` (~85 LOC) |
| `ui/settings_dialog.py` | 583-628 + load + save | „AP-Lite Diagnose" GroupBox (Block 6) + 4 keys in `_load_values` + `_save_and_close` |
| `config/settings.py` | 96-107 | 4 DEFAULTS-Keys + Kommentar-Block |
| `ui/help_dialog.py` | 17 | Tupel `("AP-Lite Rettung", "AP-Lite Rescue", "ap-lite")` aus FEATURES_INDEX |

### Kommentar-Cleanup

| Datei | Zeile | Was |
|---|---|---|
| `core/audio_dump.py` | 4 | „AP-Lite-Decode-Replay" → „Decode-Replay" |
| `tests/test_slot_display.py` | 9 | „Test-Mocks/AP-Lite-Rescue" → „Test-Mocks/Rescue" |
| `tests/test_help_dialog_features.py` | 40 | Test erwartet „AP-Lite Rettung" als sortierten Eintrag — Test anpassen (anderer Sort-Test) oder löschen |
| `tests/test_modules.py` | 2320+ | „AP-Lite — Tests in test_ap_lite.py / test_ap_lite_e2e.py" Block-Header + Tests dahinter |

### Doku-Cleanup

| Datei | Zeile | Was |
|---|---|---|
| `README.md` | 231 | `\| AP-Lite Rescue \| ...` Tabellen-Zeile |
| `README_DE.md` | 303 | ✅-Bullet AP-Lite-Beschreibung |
| `README_DE.md` | 379 | `ap_lite.py` aus Architektur-Diagramm |
| `README_DE.md` | 468 | `\| AP-Lite (QSO Rescue) \| ...` Tabellen-Zeile |
| `TODO.md` | 12-30+ | P149-Sektion ersetzen durch P151-Eintrag |

## Was NICHT angefasst wird

- `HISTORY.md` Einträge zu P149/v0.98.30 bleiben (HISTORY-Regel: nur anhängen)
- `Appsicherungen/.../ap_lite.py` Backup (Rollback)
- `~/.simpleft8/ap_lite_stats.json` (Mike-Datei)

## Reihenfolge

1. Aufrufer raus (mw_cycle, main_window) — sonst NameError im Test
2. Datenstrukturen-Felder raus (qso_state, decoder)
3. Settings + UI (settings_dialog, config, help_dialog)
4. Encoder-Methode raus
5. Modul + Tests + Docs löschen
6. Kommentar-Cleanup
7. README + TODO

## Fragen an dich

**F1 (kritisch):** Übersehe ich irgendwo eine AP-Lite-Referenz?
Mein grep:
```
grep -rn "ap_lite\|APLite\|AP-Lite\|AP_LITE" --include="*.py" --include="*.md"
```
zeigt die obigen Dateien. Reicht das, oder gibt es weitere Suchmuster
(z.B. „last_pcm_12k", „partner_last_snr", „generate_reference_wave",
„rescue_count", „get_instance" wo Singleton-Pattern)?

**F2 (Decoder-Buffer):** `decoder.last_pcm_12k` wird in Z. 332 bei JEDEM
Decode-Pass gesetzt. Wenn ich das entferne, wird trotzdem irgendwo
indirekt benötigt? Z.B. Debug-Logging?

**F3 (qso_state):** `partner_last_snr` ist im QSOData-Dataclass.
Entfernen heißt Field weg + Update-Stelle weg. Hat das Nebeneffekte
auf Serialisierung (persistente QSOs)? Wird das in eine Datei
geschrieben?

**F4 (test_modules.py):** Was ist das überhaupt? Mike hat einen
Modul-Import-Smoke-Test. Wenn ich den AP-Lite-Block rausnehme,
funktionieren die anderen Tests in der Datei weiter?

**F5 (Settings-Migration):** Wenn ein User die alten Settings-Keys
(`ap_lite_enabled` etc.) noch in `~/.simpleft8/settings.json` hat —
braucht der Code Migration (Keys ignorieren), oder ist das implizit
durch `settings.get(key, default)` schon abgesichert?

**F6 (Order):** Ist die Reihenfolge der Änderungen vernünftig, oder
würdest du anders priorisieren?

**F7 (Tests die nicht weg sollen):** Eventuell teste ich `partner_last_snr`
in einem Nicht-AP-Lite-Test? grep zeigt nur AP-Lite-Tests, aber bitte
prüfen.

## Erwartet von dir

- Findings als ROT/ORANGE/GELB
- Konkrete Stellen die ich übersehen habe (Datei + Zeile)
- KISS — keine Architekturänderungen außerhalb Removal
- „Weiß ich nicht" statt raten

Mike geht jetzt schlafen, ich entscheide. Aber ich will keine bösen
Überraschungen morgen früh.
