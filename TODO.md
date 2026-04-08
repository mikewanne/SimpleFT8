# SimpleFT8 — TODO & Roadmap

**Stand:** 08.04.2026 | **Tag:** v0.20-forward-jump-fix
**GitHub:** https://github.com/mikewanne/SimpleFT8

---

## PRIO 1: NOCH OFFEN (QSO-Logik)

- [x] **Vorwaerts-Springen im State** — qso_state.py (08.04.2026)
  - WAIT_REPORT + RR73/73 → direkt TX_73 (WSJT-X konform: sendet 73, nicht RR73)
  - TX_CALL + RR73/73 → pending → nach TX direkt TX_73
  - Fix: vorher wurde RR73 zurueckgesendet → "Double RR73 Glitch" → jetzt 73 (korrekt)

- [ ] **Even/Odd Slot bei Retries** — qso_state.py + encoder.py
  - Beim ersten CQ-Reply wird Slot jetzt korrekt gesetzt (v0.19)
  - Bei Hunt-Retries (WAIT_REPORT → retry): Slot koennte nach langer Wartezeit falsch sein
  - Pruefen ob Slot bei jedem retry neu gesetzt werden muss

- [ ] **Diversity-Messung: "MESSEN pausiert (TX)" anzeigen** — main_window.py
  - Waehrend TX wird Antenne nicht gewechselt (korrekt implementiert)
  - GUI zeigt aber kein Feedback → Operator denkt Messung haengt
  - Fix: `control_panel.update_diversity_ratio("PAUSE", ...)` waehrend TX

---

## PRIO 2: FEATURES

- [ ] **Antennen-Info im QSO Log** — qso_panel.py + main_window.py
  - Bei Diversity: zeigen auf welcher Antenne die Antwort empfangen wurde
  - z.B. `10:00 ← DA1MHH R1BEO KP50  [A2]` im QSO Verlauf

- [ ] **Logbuch: QSO loeschen** — logbook_widget.py + adif.py
  - Delete-Button im Overlay vorhanden, ADIF-Loesch-Logik fehlt

- [ ] **Logbuch: QSO editieren + speichern** — qso_detail_overlay.py
  - Save-Button vorhanden, Rueckschreiben in ADIF fehlt

- [ ] **QSO-Resume aus QSO-Panel** — qso_state.py
  - Station im QSO-Verlauf anklicken → QSO fortfuehren

- [ ] **FT4-Modus** — 7.5s Zyklen, andere Frequenzen

- [ ] **Band Map / Spot Aggregation** — PSKReporter + DX Cluster als Input

---

## PRIO 3: ARCHITEKTUR (langfristig)

- [ ] **SessionController/Engine extrahieren** — main_window.py (~1300 Zeilen)
  - Diversity-Logik, Power-Regelung, Meter-Handling, QSO-Flow raus aus UI

- [ ] **FlexRadio Klasse aufteilen** — flexradio.py (~1300 Zeilen)
  - ProtocolHandler / AudioStreamManager / MeterParser

---

## ERLEDIGT (chronologisch)

### 08.04.2026
- [x] **Even/Odd Slot Fix (CQ-Modus)** — qso_state.py + main_window.py
  - `tx_slot_for_partner` Signal: CQ-Reply Slot → encoder.tx_even = Gegentakt
  - Behebt: UR4QWW-Muster (Station empfaengt unsere Reports nicht)
- [x] **73 nach QSO blockiert CQ** — qso_state.py
  - BLOCK 1: kein `return` mehr bei 73 waehrend CQ-States
  - `_resume_cq_if_needed()`: timeout_cycles = 0 reset
  - `_on_state_changed()`: CQ-Button bleibt aktiv bei CQ_CALLING/CQ_WAIT

### 07.04.2026 (v0.16–v0.18)
- [x] Memory Leak: `_responses` Dict begrenzt auf 200 Eintraege
- [x] Thread-Safety: `copy.copy()` vor FT8Message Mutation
- [x] `advance()` sendet R-Report (nicht plain Report)
- [x] AP-Decoder priority_call fix: `qso_sm.qso.their_call`
- [x] QRZ Lookup + Bulk Upload non-blocking (ThreadPoolExecutor)
- [x] Duplicate ADIF Parser: qso_log.py importiert aus adif.py
- [x] rfpower +15% Headroom fuer linearen PA-Betrieb
- [x] PI-Controller (asymmetrisch, Kp_up/Kp_down/Ki)
- [x] TX Level Bar mit "TX" Label beschriftet
- [x] Bandwechsel stoppt CQ, QSO, TX, leert QSO-Log
- [x] HALT Button (Notaus, rot, immer aktiv)
- [x] Gesamt-QSO Timeout 3 Min (MAX_QSO_DURATION=180)
- [x] Retry-Limits: MAX_STATION_CALLS=7, MAX_RR73_RETRIES=3
- [x] RRR als Bestaetigung (is_rr73 prueft "RRR" + "RR73")
- [x] RR73/R-Report waehrend TX_REPORT: pending queue
- [x] WAIT_RR73 endlos-Retry fix
- [x] README.md: EN + DE auf einer GitHub-Seite
- [x] Docs EN+DE: DIVERSITY, DX_TUNING, POWER_REGULATION

### Vor 07.04.2026
- [x] Auto TX Power Regulation, Peak-Monitor, 10 Power Buttons
- [x] Integriertes Logbuch, QSO Detail Overlay, QRZ.com API
- [x] Temporal Polarization Diversity, UCB1, DX Tuning
- [x] VITA-49 TX (int16 mono 24kHz), FT8 Decoder Pipeline
- [x] ADIF 3.1.7 Logging, PSKReporter Integration

---

*08.04.2026 — DA1MHH / Mike + Claude + DeepSeek*
