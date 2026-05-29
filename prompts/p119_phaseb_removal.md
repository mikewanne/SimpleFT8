# R1-Review — P119: 10-W-Einpendeln (Phase B) + Hochrechnungs-Krücke entfernen

## Was ich von dir will
Du bist Reviewer für sicherheitskritischen Funkgeräte-Code (FlexRadio TX).
KEIN Code generieren. Nur Findings nach Severity (🔴 BLOCKER / 🟠 WICHTIG /
🟡 HINWEIS / 🟢 OK), je: Datei:Zeile · Was · Warum · Vorschlag. Knapp.
Am Ende: klare Scope-Empfehlung + GO/NO-GO. KISS bewerten (Overengineering
vermeiden). Code ist die Referenz — wenn meine Annahmen unten dem Code
widersprechen, sag es.

## Kontext (Mike, Hobby-Funker, FlexRadio 6400)
SimpleFT8. Bei jedem TUNE (manueller TUNE-Button, Auto-TUNE bei Bandwechsel,
Kontroll-TUNE in der Gain-Messung) läuft nach dem Tuner-Match eine "Phase B":
`_tune_converge_to_target(target_w=10)` pendelt die Sendeleistung per Closed-Loop
auf FWDPWR≈10 W ein. Der dabei gefundene rfpower-Slider-Wert wird als
RFPreset-Stützpunkt `{band}_10W` gespeichert. Dieser 10-W-Anker dient zwei
Zwecken: (a) `_kruecken_skalierung` rechnet ihn linear auf die Ziel-Wattzahl
(z.B. 70 W) hoch = Startwert für den ersten Bandbesuch; (b) `has_anchor(watt=10)`
entscheidet, ob Auto-TUNE bei Bandwechsel übersprungen wird.

**Mike will Phase B + Krücke entfernen.** Begründung (verifiziert im Code):
Der normale Betrieb `_auto_adjust_tx_level` (mw_tx.py:959-968) speichert beim
Einpendeln auf die ECHTE Ziel-Wattzahl bereits `rf_preset_store.save(radio,
band, watts, rf)` — also `{band}_70W` direkt. Die 10-W→70-W-Hochrechnung ist
damit nur ein grober Startwert-Schätzer für den allerersten Bandbesuch und
überflüssig. Zusätzlich trifft die 10-W-Konvergenz das Ziel oft nicht sauber
("bleibt bei 11 W"), die Anzeige "Leistung wird auf 10 W eingeregelt" ist also
auch UX-Ballast.

## V1/V2 — geplanter Eingriff (gegen echten Code geprüft)
ENTFERNEN:
1. `mw_tx.py:_tune_stop` Z.352-362: Phase-B-Aufruf
   `_tune_converge_to_target(target_w=10)`. **Der SWR-Freeze (Z.330-334,
   `swr_after_match = _compute_match_swr()`) läuft VOR Phase B (P142) und BLEIBT
   unangetastet** — meine Kernannahme: die Band-Sperre/SWR-Sicherheit
   (P53/P142/P153/P159) ist von Phase B unabhängig.
2. `mw_tx.py:_tune_post_swr_check` Z.483-508: Speicherung des 10-W-Stützpunkts
   (`rf_preset_store.save(radio, band, 10, rf_to_save)`) + zugehörige
   `_apply_rf_preset()`/`set_power`-Sync.
3. `mw_tx.py:_kruecken_skalierung` (Z.661-693) + Aufruf in `_apply_rf_preset`
   (Z.66-70). `_apply_rf_preset` fällt dann bei `load()==None` direkt auf
   `settings.get_tx_power(band, default=50)`.
4. `mw_tx.py:_tune_converge_to_target` (Z.587-659) — toter Code nach (1).
5. dx_tune_dialog.py Z.374-381 + auto_tune_dialog.py Z.176-177: die
   "Leistung wird auf 10 W eingeregelt"-Anzeige (else-Zweig nach TUNE-Dauer).

BLEIBT: Phase A (Tuner-Match), SWR-Freeze + Median (P142/P153/P159),
Band-Sperre, Post-Check, `_auto_adjust_tx_level` (speichert {band}_{watts}).

## Risiko-Liste (bitte bewerten)
- **R1 🔴 has_anchor:** `mw_radio.py:643-694` skippt Auto-TUNE bei Bandwechsel
  wenn `has_anchor(radio, band, watt=10)` True. Ohne 10-W-Save ist der Anker nie
  mehr da → Auto-TUNE läuft bei JEDEM Bandwechsel. Optionen: (a) `has_anchor`
  auf "irgendein Stützpunkt für das Band existiert" umstellen (watt-agnostisch);
  (b) Auto-TUNE-Skip ganz streichen (immer tunen). Was ist richtig/KISS? Mike
  hat ein separates Setting "Auto-TUNE bei Bandwechsel" (an/aus).
- **R2 🔴 SWR-Sicherheit:** Stimmt meine Annahme, dass Phase B KEINEN Einfluss
  auf `_tune_last_valid_swr`/Post-Check/Band-Sperre hat (Freeze ist davor)?
  Übersehe ich einen Pfad, wo Phase B den SWR-Stream oder die Bewertung
  beeinflusst?
- **R3 🟠 Startwert erster Bandbesuch:** Ohne Krücke startet
  `_auto_adjust_tx_level` von `get_tx_power(default=50)` statt vom
  hochgerechneten Anker. Closed-Loop pendelt eh ein (RF_STEP_MAX begrenzt
  Sprünge). Hardware-Risiko bei Start aus 50 statt z.B. 63? FlexRadio 6400,
  ANT1, Antennen-Tuner.
- **R4 🟡 _tune_converged_rf:** Nach (1) immer None → in post_check `rf_to_save`
  = hart 10. Sauberer ganz entfernen (mit (2))?
- **R5 🟡 Tests:** test_p54_fix / p142 / p74a / p71 / p76b/c prüfen Phase
  B / Krücke / Anker. Welche Aussagen kippen erwartbar?

## Konkrete Fragen
1. R1 + R2 sind die Blocker — bewerte beide gegen den echten Code.
2. Empfiehl den minimalen, sichersten Scope. Soll die Krücke wirklich GANZ raus
   oder reicht es, nur Phase B + Anzeige zu entfernen und den 10-W-Save zu
   lassen (dann hätte has_anchor weiter einen Anker)?
3. Edge-Cases die ich übersehe (Cancel während TUNE, Disconnect, Re-Tune-Race)?
4. GO/NO-GO + KISS-Urteil.
