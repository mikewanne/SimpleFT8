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

## PRIO 5: FEATURES

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
