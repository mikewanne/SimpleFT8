# SimpleFT8 — TODO & Roadmap

**Stand:** 07.04.2026 | **Tag:** v0.15-logbook-docs
**GitHub:** https://github.com/mikewanne/SimpleFT8

---

## PRIO 1: KRITISCHE BUGS (Code Review 07.04.2026)

- [ ] **Memory Leak: `_responses` Dict waechst unbegrenzt** — flexradio.py:59
  - Fire-and-forget Responses werden nie geloescht
  - Fix: Alte Eintraege nach 30s entfernen oder Dict-Groesse begrenzen

- [ ] **Thread-Safety: FT8Message wird aus Decoder-Thread mutiert** — decoder.py + main_window.py
  - `msg.antenna = ant` wird im GUI-Thread gesetzt waehrend Decoder-Thread msg referenziert
  - Fix: Kopie der Message erstellen bevor GUI sie modifiziert

- [ ] **advance() sendet plain report statt R-report** — qso_state.py:410
  - In WAIT_REPORT nach Empfang eines plain reports wird "-10" statt "R-10" gesendet
  - Muss geprueft werden ob das der Grund fuer weitere Timeouts ist

- [ ] **AP-Decoder priority_call ist immer leer** — main_window.py:1054
  - `getattr(self.qso_sm, 'their_call', '')` — falsches Attribut
  - Richtig: `self.qso_sm.qso.their_call`
  - Effekt: AP-Dekodierung mit Prioritaet fuer aktive Station funktioniert nicht

---

## PRIO 2: PERFORMANCE + STABILITÄT

- [ ] **QRZ Lookup blockiert GUI-Thread** — main_window.py:1146
  - HTTP Request bis 10s → UI eingefroren
  - Fix: In QThread oder concurrent.futures auslagern

- [ ] **QRZ Bulk Upload blockiert GUI-Thread** — main_window.py:1182
  - Loop ueber alle QSOs mit HTTP pro QSO → langer Freeze
  - Fix: Background Worker mit Fortschrittsanzeige

- [ ] **Duplicate ADIF Parser** — log/adif.py + log/qso_log.py
  - Zwei verschiedene Implementierungen
  - Fix: Einen Parser verwenden, den anderen loeschen

- [ ] **Duplicate qso_state Datei** — core/qso_state 2.py
  - Alte Version, muss geloescht werden

- [ ] **Logbook nutzt eigene kleine Prefix-Map** — logbook_widget.py:27
  - Hat nur ~40 Laender, core/geo.py hat 300+
  - Fix: geo.py importieren statt eigene Map

---

## PRIO 3: TX POWER OPTIMIERUNG

- [ ] **rfpower 15% ueber Zielwert setzen** — main_window.py
  - Statt rfpower=70 → rfpower=80 setzen, Audio-Drive reduzieren
  - PA arbeitet linearer = saubereres Signal
  - Peak sollte bei 85-90% liegen, nicht bei 58%

- [ ] **PI-Controller statt P-Controller** — main_window.py
  - Integral-Term fuer nachhaltige Fehler > 30s
  - Verhindert dauerhaftes Unter-/Uebersteuern

- [ ] **TX Level Bar beschriften** — control_panel.py
  - "TX" oder "RF" Label vor den Balken setzen
  - Balken ggf. kleiner machen

---

## PRIO 4: ARCHITEKTUR-REFACTORING

- [ ] **SessionController/Engine extrahieren** — main_window.py (~1300 Zeilen)
  - Diversity-Logik, Power-Regelung, Meter-Handling, QSO-Flow raus aus UI
  - MainWindow wird reine View
  - Ermoeglicht Unit-Tests und Headless-Betrieb

- [ ] **FlexRadio Klasse aufteilen** — flexradio.py (~1300 Zeilen)
  - ProtocolHandler (TCP/UDP)
  - AudioStreamManager (VITA-49 RX/TX)
  - MeterParser (FWDPWR, SWR, ALC)

- [ ] **`hasattr` Anti-Pattern entfernen** — flexradio.py
  - `_pcc_seen`, `_lvl_dbg_t`, `_alc_dbg` in `__init__` initialisieren

---

## PRIO 0: SOFORT (Bandwechsel-Schutz)

- [ ] **Bandwechsel stoppt ALLES** — main_window.py `_on_band_changed()`
  - CQ-Modus sofort stoppen (`qso_sm.stop_cq()`, CQ-Button reset)
  - Laufendes QSO abbrechen (`qso_sm.cancel()`)
  - Diversity-Messung abbrechen wenn aktiv
  - Encoder TX stoppen falls gerade gesendet wird
  - QSO-Panel (Live Log) leeren — neues Band = neuer Kontext
  - Aktuell: Band wechselt aber CQ/QSO laufen auf der alten Frequenz weiter!

- [ ] **HALT Button (Notaus)** — qso_panel.py oder control_panel.py
  - Ein Button der ALLES sofort stoppt: CQ, QSO, TX, Messung
  - Gut sichtbar im QSO-Bereich (rot, gross)
  - Wie ein Panic-Stop — egal was gerade laeuft, alles wird abgebrochen
  - Setzt State Machine auf IDLE, CQ-Modus aus, TX aus

---

## PRIO 1.5: QSO LOGIK VERBESSERUNGEN

- [ ] **Even/Odd Slot Tracking (KRITISCH!)** — qso_state.py + timing.py
  - Aktuell: kein explizites Slot-Tracking
  - Regel: Antwort IMMER im Gegen-Slot (wenn er im even sendet, wir im odd)
  - Bei Empfang: rx_slot merken, tx_slot = Gegenteil
  - Bei Slot-Verlust: re-sync anhand empfangener Nachricht
  - WSJT-X macht das — vermutlich Hauptursache fuer viele Timeouts!

- [ ] **Gesamt-QSO Timeout (3 Min)** — qso_state.py
  - Unabhaengig von einzelnen Retry-Countern
  - Wenn 3 Minuten ohne Fortschritt (kein State-Wechsel vorwaerts) → aufgeben
  - Verhindert ALLE "endlos senden" Szenarien

- [ ] **RRR als Bestaetigung akzeptieren** — qso_state.py
  - Manche Stationen senden RRR statt RR73
  - Beides als Bestaetigung werten → TX_RR73 oder WAIT_73

- [ ] **Retry-Limits differenzieren** — qso_state.py
  - **Anruf auf Station (Hunt + CQ-Antwort):** max 7 Versuche (hart), auch wenn 99 eingestellt
  - **CQ Rufe:** max_calls aus Settings (3/5/7/99) — CQ darf lang laufen
  - **WAIT_RR73 Retry:** max 3 (wenn nach 3x Report wiederholen keine Antwort → aufgeben)

- [ ] **Vorwaerts-Springen im State** — qso_state.py
  - Wenn Nachricht empfangen die WEITER im Ablauf ist als erwartet → State ueberspringen
  - z.B. in WAIT_REPORT aber RR73 empfangen → direkt zu TX_RR73
  - WSJT-X macht das fuer maximale Flexibilitaet

- [ ] **GitHub Docs auch auf Deutsch** — docs/
  - DIVERSITY.md → DIVERSITY_DE.md
  - DX_TUNING.md → DX_TUNING_DE.md
  - POWER_REGULATION.md → POWER_REGULATION_DE.md
  - README_DE.md: Links zu deutschen Docs aktualisieren

---

## PRIO 5: FEATURES

- [ ] **Antennen-Info im QSO Log** — qso_panel.py + main_window.py
  - Bei Diversity: zeigen auf welcher Antenne die Antwort empfangen wurde
  - z.B. `10:00 ← DA1MHH R1BEO KP50  [A2]` im QSO Verlauf
  - Bestaetigung fuer den Operator: "Die Station kam ueber ANT2 rein!"
  - Braucht: aktuelle Antenne aus Diversity-Controller an QSO-Panel durchreichen

- [ ] **QSO-Resume aus QSO-Panel** — qso_state.py
  - Station im QSO-Verlauf anklicken → QSO fortfuehren
  - `qso_sm.force_resume(their_call, state)` noetig

- [ ] **Logbuch: QSO loeschen** — logbook_widget.py + adif.py
  - Delete-Button ist im Overlay, aber ADIF-Loesch-Logik fehlt noch

- [ ] **Logbuch: QSO editieren + speichern** — qso_detail_overlay.py
  - Save-Button ist da, aber Rueckschreiben in ADIF fehlt

- [ ] **FT4-Modus** — 7.5s Zyklen, andere Frequenzen

- [ ] **Band Map / Spot Aggregation** — PSKReporter + DX Cluster als Input

---

## ERLEDIGT (07.04.2026)

- [x] Auto TX Power Regulation (P-Controller + FWDPWR Feedback)
- [x] Asymmetrische Regelung (runter 2x schneller als hoch)
- [x] Clipping-Schutz (Peak-Monitor, stoppt bei >95%)
- [x] Per-Band TX Level Speicherung
- [x] 10 Power Buttons (10-100W)
- [x] Peak-Anzeige statt ALC
- [x] TX Level Bar (automatisch, keine manuelle Bedienung)
- [x] max_power_level=100 bei jedem set_power()
- [x] mic_level Steuerung via set_tx_level()
- [x] WAIT_RR73 Retry (Report wird wiederholt wenn RR73 ausbleibt)
- [x] QSO Debug Logger (qso_debug.log, wird pro QSO ueberschrieben)
- [x] Integriertes Logbuch (Tab im QSO Panel)
- [x] QSO Detail Overlay (Klick → Details + QRZ Lookup)
- [x] QRZ.com API Client (Upload + Callsign Lookup)
- [x] RADIO Kachel Redesign (PSK Frame, TX Frame, Trenner)
- [x] Karten-Rahmen: Top-Akzent-Strip
- [x] README EN + DE + 3 Innovation Docs
- [x] Diversity UnboundLocalError fix (diff bei total=0)
- [x] Ehrliche Performance-Tabelle (nur belegte 40m Daten)

---

*07.04.2026 — DA1MHH / Mike + Claude + DeepSeek*
