# P71 Auto-Tune Bundle — R1 Review-Anfrage an DeepSeek-V4-pro

Du bist DeepSeek-V4-pro. Du bekommst V2 (Self-Review-Plan) + die fünf
relevanten Code-Files. Bitte führe Code-Review durch und gib strukturiert
zurück.

## Kontext

**Projekt:** SimpleFT8 — FT8/FT4/FT2-Funker-Tool für FlexRadio.
**Stand:** v0.97.46, Tests 1435 grün. Hardware-Pflicht **ANT1=TX only**,
ANT2 niemals TX (Hardware-Schaden möglich).

**P71 Auftrag:** Bugfix-Bundle für AutoTuneDialog nach Mike-Field-Test
18.05.2026 morgens. 5 Punkte:

1. **Backup-Timer-Race:** Backup `(duration_s + 5) * 1000` = 20 s zu eng
   gegen worst-case 15 + 6.5 + 2 = 23.5 s → Timeout-Modal trotz erfolg-
   reichem TUNE bei SWR 1.9.
2. **App-Start triggert Auto-Tune ungewollt:** Mike beobachtet, dass
   beim ersten Start ohne 10-W-Anker im RFPresetStore Auto-Tune feuert.
   Trigger-Pfad NICHT eindeutig identifiziert (Hypothesen H1/H2/H3 in V2).
3. **Settings tune_duration_s 15/30 → 5/10/15** (Mike-Spec für FT8/FT4/FT2-Differenzierung).
4. **AutoTuneDialog-UX:** Title "Auto-TUNE läuft — 15M" verwirrend
   (sieht aus wie 15 Minuten). Plus Mode + Live-FWDPWR fehlen.
5. **Auto-Tune-Logging:** klare DONE OK/FAIL-Zeilen fehlen für
   Diagnose-Grep in datierter Log-Datei.

## Bisherige Workflow-Schritte

- V1: `prompts/p71_autotune_bundle_v1.md` (Initial-Plan).
- V2 (Self-Review): `prompts/p71_autotune_bundle_v2.md` (← Hauptdokument für dich).

**Bitte gegen V2 reviewen — V1 nur als historische Referenz.**

## Code-Files im Anhang

1. **`ui/auto_tune_dialog.py`** — AutoTuneDialog (Modal, Spinner, Backup-Timer,
   Cancel, Signal-Slot für auto_tune_done).
2. **`ui/mw_tx.py`** — TX-Pipeline. Relevante Methoden:
   - `_start_auto_tune_for_band_change` (Z.453)
   - `_tune_stop` (Z.139)
   - `_tune_post_swr_check` (Z.212)
   - `_tune_converge_to_target` (Z.343)
   - `_wait_with_event_loop` (Z.331)
3. **`ui/mw_radio.py`** — `_on_band_changed` (Z.380) mit Auto-Tune-Hook (Z.498-506).
4. **`ui/settings_dialog.py`** — ComboBox `tune_duration_combo` (Z.331-338,
   605-606, 765, 813).
5. **`ui/main_window.py`** — `__init__` mit Init-Reihenfolge `_set_band` →
   `_start_radio` (Z.90-123) UND `band_changed.connect` (Z.736).

## Aufgabe

Bitte 4-Level-Review mit klarer Klassifikation:

### Klassifikations-Schema (PFLICHT)

- 🔴 **ROT (Bug):** echter Bug der Code bricht ODER User-sichtbares
  Fehlverhalten. MUSS gefixed werden vor Push.
- 🟠 **ORANGE (Risiko):** Race-Condition, Edge-Case, fehlender Cleanup-Pfad.
  Wahrscheinlich nicht im Alltag, aber latent gefährlich.
- 🟡 **GELB (Verbesserung):** Code-Qualität, Wartbarkeit, Defensive,
  Naming. Optional aber empfohlen.
- ⚪ **HINWEIS:** Akademisch, Stil, Doku.

### Schwerpunkte deines Reviews

1. **Bug 2 Wurzel-Diagnose:** Welche Hypothese (H1/H2/H3) ist richtig?
   Falls keine: was ist der echte Trigger-Pfad? Bitte konkret Code-Zeilen
   nennen. **Insbesondere:** Feuert `ControlPanel._set_band(band)` das
   `band_changed`-Signal auch wenn der Slot noch nicht connect-bar ist
   (Z.103 vor Z.736)?

2. **Backup-Timer-Grace:** Ist `+12 s` ausreichend? Müssten wir bei
   konfigurierbarer Dauer (5/10/15) den Grace-Anteil dynamisch
   skalieren (z.B. min 12, max 15 für längere Phase-B-Fenster)?
   Phase B ist HART begrenzt auf 6.5 s — unabhängig von duration_s.

3. **Settings-Migration-Robustheit:** ComboBox `findData()`-Umstellung
   ausreichend? Was passiert wenn alter Wert 30 nicht im Items-Set ist
   (findData returnt -1)?

4. **FWDPWR-Live-Lesen im Dialog:** Direkter Zugriff auf
   `parent._fwdpwr_samples[-1]` ist tight coupling. Saubere Alternative:
   neue Property `radio.last_fwdpwr`? Oder dispatch über Signal? KISS-
   Trade-off bitte einschätzen.

5. **Logging-Format:** ist `[P54a] DONE OK band=... swr=... fwdpwr=...
   rf=... duration=...s` der richtige Format-Stil für grep-Auswertung?
   Sollte Mode + Antenne auch rein? Mehrzeilen-Block vs. 1-Zeile?

6. **Hardware-Pflicht (ANT1-Check):** Auto-Tune-Pfad ruft
   `set_tx_antenna("ANT1")` vor `tune_on()` (mw_tx.py:492). Bei
   Cancel-Pfad / Backup-Timeout-Pfad keine ANT2-Setzung. Sicher genug
   oder fehlt explizite ANT1-Verifikation?

7. **Test-Coverage:** Die 11 V2-Tests reichen? Was fehlt?

8. **Push-Freigabe:** Wenn alle ROT/ORANGE-Punkte addressiert sind —
   freigegeben für Code-Phase oder gibt es noch Blocker?

### Bitte gib zurück

- Findings F1, F2, ... mit Klassifikation + 1-2 Sätze Begründung + 1-2
  Sätze Lösungsvorschlag.
- Bei Bug 2: konkrete Code-Zeilen-Referenzen.
- Push-Freigabe-Empfehlung: "PUSH FREIGABE NACH Findings F1-Fx" oder
  "BLOCKER".

**Halluzinations-Check:** Falls du Code-Stellen referenzierst die nicht
in den angehängten Files sind — **explizit markieren als „unverifiziert,
bitte Mike/Claude prüfen"**, nicht als Fakt.

Halte dich kurz und präzise. Maximal 1500 Wörter.
