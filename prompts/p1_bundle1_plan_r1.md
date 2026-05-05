# P1-Bundle1 Plan-R1 Findings (DeepSeek-Reasoner)

**Stand:** 2026-05-06.
**Tokens:** in=81634 out=7077 total=88711.
**Workflow:** Plan-V1 → Plan-V2 → **Plan-R1** (diese Datei) → Plan-V3.

---

## Hidden Bugs
- **B1 (Test-Fixture Konflikt):** V3-Tests verwenden `qtbot` (pytest-qt). Der Repo verwendet eigene `_ensure_app()`. Die Tests werden mit `qtbot` nicht laufen.
  → **Bereits in Plan-V2 als L1 adressiert.**
- **B2 (P1.15-Test nur Stub):** `pass` ist nicht implementiert. Keine Regression guard.
  → **Bereits in Plan-V2 als L6 (grep-Test) adressiert.**
- **B3 (`_append_two_color` ohne Timestamp-Test):** Kein Test fuer `_append_two_color` Timestamp-Setzung.
  → **NEU in Plan-V3 ergaenzen (T1).**
- **B4 (StarsConditionWidget Clamping nicht getestet):** `set_score(0)` / `set_score(6)` ungestestet.
  → **NEU in Plan-V3 ergaenzen (T2).**

## Edge Cases
- **E1:** `_auto_trim_by_age` Schwelle `n_old < 5` — Flatterschutz, akzeptabel.
- **E2:** `compute_local_conditions` Performance bei >500 Stationen — nicht kritisch.
- **E3:** `_append_two_color` Timer-Erfassung implizit — wird durch B3/T1 explizit.

## Tests Erweiterungen
- **T1:** `test_qso_panel_two_color_timestamp_appended` — analog zu `_append_colored`-Test.
- **T2:** `test_stars_widget_clamping_low` (score=0 → 1) + `test_stars_widget_clamping_high` (score=6 → 5).
- **T3:** P1.15 Source-Grep — bereits in Plan-V2.
- **T4:** `qtbot` → `_ensure_app()` — bereits in Plan-V2.

## KISS-Verstoesse
- **K1:** Keine.

## Backward-Compat
- `update_snr()` wird No-Op → Caller laufen weiter, keine Crash.
- `remeasure_clicked` Signal + Handler entfernt → keine externen Nutzer.
- Statuslabel `→ Call | RX: ANT` entfaellt → kein externer Zugriff.
- Retro-Kompatibel.

## Empfehlung Gesamt
**Plan freigegeben unter Bedingungen:**
- T1–T4 vor Code-Implementation umsetzen.
- Danach Code-Implementation. Keine Architektur-Aenderungen noetig.
