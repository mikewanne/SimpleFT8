# P1.BUNDLE2 — Self-Review V2 (rolle: frische KI prueft V1)

**Auftrag:** V1 kritisch lesen, Luecken/Mehrdeutigkeiten benennen, V3-Plan
schaerfen. **NICHT** das Problem loesen, sondern den Plan verbessern.

---

## Lessons aus V1

### L1 — P1.11 Option A vs B Trade-off NICHT entschieden

V1 §1 nennt Option A (neues Feld) als „sauber, KISS" und Option B
(Reset bei WAIT_73-Entry) als Alternative ohne klare Empfehlung.

**Entscheidung V2:** Option A. Begruendung:
- Reset waere fragil — bei welchen State-Eintritten genau? `_set_state(WAIT_73)`
  passiert in `on_message_sent` wenn `state == TX_RR73`. Reset dort wuerde
  laufenden WAIT_RR73-Retry-Counter ueberschreiben falls QSO doch noch
  in Schleife rutscht (race-anfaellig).
- Neues Feld ist 1 Zeile in QSOData + 2 Zeilen Aenderung in WAIT_73 →
  identischer Code-Footprint, aber semantisch sauber getrennt.
- Test-Coverage einfacher (beide Counter unabhaengig pruefbar).

→ V3 nimmt Option A.

### L2 — P1.13 Diversity-Mode-Filter ist KRITISCH

V1 §2 hat `if self._rx_mode == "normal":` davor, V2 bestaetigt das ist
korrekt. Im Diversity-Modus uebernimmt `_diversity_ctrl.get_free_cq_freq()`
die TX-Suche; Hunt-Klick im Diversity wuerde mit der Auto-Suche kollidieren.

Aber V1 vergass den **Edge-Case `_rx_mode in ("dx_tuning", "gain_measure")`**
— waehrend Kalibrier-Pipeline koennte ein Klick durchrutschen.

**V2-Verschaerfung:** Filter strikt auf `== "normal"` statt
`!= "diversity"`. V1 hat das schon richtig formuliert — V2 bestaetigt.

### L3 — P1.13 `_diversity_ctrl.get_histogram_data()` Falle

V1 §2-Fix ruft `self._diversity_ctrl.get_histogram_data()` im Normal-Modus
auf. Pruefe: liefert das im Normal-Modus sinnvolle Daten? `core/diversity.py`
sammelt Bins jeden Slot, unabhaengig vom Modus → Daten existieren immer.
ABER: im Normal-Modus wird das Histogramm vermutlich gar nicht
gerendert (nur Diversity-Panel hat das Widget). Der Aufruf koennte
unnoetig sein.

**V2-Schaerfung:** Pruefen ob `control_panel._freq_hist` im Normal-Modus
ueberhaupt sichtbar ist. Wenn nicht: Aufruf weglassen, nur Encoder + Spinbox.

→ V3 hat **2 Varianten** (mit/ohne Histogramm-Update) — Code-Verifikation
in V3-Phase entscheidet.

### L4 — P1.7 Antennen-Stats-Frage offen (V1 Q4)

V1 fragt: bei Duplikat-Skip auch `_stats_logger.log_antenna_qso` skippen?

**V2-Antwort:** JA, alles skippen. Antennen-Stats messen Empfangs-
qualitaet pro Call/Antenne — ein Doppel-Eintrag binnen 5 Min hat keinen
Mehrwert (gleiche Bedingungen). Skip vermeidet Bias.

### L5 — P1.7 Cache-Persistenz NICHT noetig (V1 hat Recht)

V1 §3 Wichtig-Block: Cache Session-lokal, nicht persistent. V2 bestaetigt:
- App-Restart = Mike will Status reset (z.B. nach Bug-Fix testet er
  bewusst die selbe Station nochmal).
- 5-Min-Window ist eng genug dass Persistenz zwischen App-Sessions
  ueberfluessig ist (Mike laesst die App selten nur 30s liegen).

### L6 — P1.7 Multi-Band-Edge-Case

V1 ignoriert: gleicher Call auf VERSCHIEDENEN Baendern innerhalb 5 Min.
Beispiel: 20m FT8 mit DA1TST → 21:00 UTC, dann Bandwechsel auf 40m
und DA1TST ruft 21:03 UTC erneut. Beide QSOs sind LEGITIM (separate Bands).

**V2-Schaerfung:** Cache-Key sollte `(call, band)` Tupel sein, nicht nur
`call`. So wird Multi-Band sauber unterstuetzt.

```python
self._recent_logged_calls: dict[tuple[str, str], float] = {}
key = (qso_data.their_call.upper(), self.settings.band.upper())
```

→ V3 nimmt Tupel-Key.

### L7 — P1.7 Mode-Edge-Case

Analog L6: gleicher Call, gleiches Band, aber FT8 vs FT4 vs FT2.
Realistisch sehr selten (Mode-Wechsel + dieselbe Station erneut < 5 Min)
aber theoretisch legitim.

**V2-Entscheidung:** `(call, band)`-Key reicht — Mode-Wechsel innerhalb
5 Min ist Mike's Hobby-Praxis quasi nie. KISS schlaegt Vollstaendigkeit.

### L8 — P1.7 5-Min-Konstante zentral

V1 macht `_LOG_DEDUP_WINDOW_S = 300` Modul-Konstante. V2: 5 Min ist gut.
Mike's „< 5 Min" aus TODO 2026-05-05 ist die Spec. Nicht konfigurierbar
machen (over-engineered fuer Hobby-Tool).

### L9 — Test-Konventionen Bundle-2

V1 listet 11 Tests, V2 schlaegt MEHR Edge-Cases vor um R1 nicht bemerken
zu lassen wir haetten was uebersehen:

**Zusatz-Tests:**
- P1.11: 4. Test fuer `wait_73_retries` Reset-Verhalten zwischen QSOs
  (nach `start_qso(...)` muss er wieder 0 sein da `qso = QSOData(...)`).
- P1.13: 5. Test fuer Persistenz-NICHT-Aufruf
  (`settings.save_normal_tx_freq` darf nicht aufgerufen werden bei Hunt-Klick).
- P1.7: 5. Test fuer Multi-Band-Key (selber Call, anderes Band, < 5 Min →
  beide loggen).

→ V3 Tests-Soll: 4 + 5 + 5 = **14 Tests**. 938 → **952** erwartet.

### L10 — P1.13 freq_hz=0 Edge-Case

`msg.freq_hz` kann theoretisch 0 sein (z.B. wenn Decoder die Frequenz
nicht liefert). V1 hat `if msg.freq_hz:` als Wahrheits-Check — bei 0
wird der ganze Block uebersprungen. Korrekt.

V2: bestaetigt. Aber explizit kommentieren: „Falls msg.freq_hz=0 (Decoder-
Edge-Case): keine Aenderung, Spinbox bleibt auf altem Wert".

### L11 — P1.7 Test fuer log_antenna_qso-Skip

L4-Entscheidung „auch skippen" braucht expliziten Test:
`test_p1_7_duplicate_skips_antenna_stats_too` — pruefen dass
`_stats_logger.log_antenna_qso` NICHT aufgerufen wird bei Duplikat.

→ Test-Soll: 4 + 5 + **6** = **15 Tests**.

### L12 — P1.13 Frequenz-Range 150-2800 Hz Konstante

V1 hardcodet `max(150, min(2800, ...))`. V2 prueft: stehen 150/2800
schon als Konstanten in `control_panel.py`? Spinbox hat
`setRange(150, 2800)`. → Mike's Spinbox-Spec.

**V2-Schaerfung:** Range aus Spinbox-Properties lesen statt hardcoden:
```python
spin = self.control_panel._tx_freq_spin
freq_hz = max(spin.minimum(), min(spin.maximum(), int(msg.freq_hz)))
```

So bleibt der Code automatisch konsistent wenn Mike die Range mal aendert.

### L13 — V3 Implementations-Reihenfolge wichtig

Weil 3 Bugs in 3 verschiedenen Files, sind Commit-Splits kritisch fuer
Bisect-Sauberkeit (Lesson aus v0.95.18 wo log/adif.py 2 Bugs teilte
und git-add-p Probleme machte). V2-Reihenfolge:

1. Bug 1 (P1.11): `core/qso_state.py` — isoliert.
2. Bug 2 (P1.13): `ui/mw_qso.py` — isoliert.
3. Bug 3 (P1.7): `ui/main_window.py` (Init) + `ui/mw_qso.py` (Filter-Logik)
   — `mw_qso.py` ueberschneidet sich mit Bug 2 → diese 2 Bugs muessen
   in der RICHTIGEN Reihenfolge committed werden, oder Bug-2 + Bug-3
   in EINEM Commit (V3 entscheidet).

**V2-Empfehlung:** P1.7 und P1.13 in EINEM `mw_qso.py`-Commit kombinieren
ist okay, weil beide UI-Reaktion + State-Sync sind. Alternativ git-add-p
mit verschiedenen Funktionen — geht weil `_on_station_clicked` und
`_on_qso_complete` getrennte Funktionen sind. **V3 nimmt git-add-p-Trennung**
weil es atomar bleibt.

### L14 — Kein Compact-Bedarf nach V2 — schon kompakt

V2 schlaegt nicht vor Bundle-Scope zu reduzieren. Workflow lohnt sich:
- 3 unabhaengige Diagnosen
- 3 Test-Suites
- 1 Final-R1 fuer alles

Compact zwischen Plan und Code wie v0.95.18 — ja.

### L15 — Mike-Field-Test-Pflicht?

P1.11 + P1.13 brauchen Mike-Field-Test (Funkbetrieb). P1.7 ist hardware-frei
testbar (im Test-Loop). Mike's Bundle-Praxis: alle 3 Bugs in einer Push-
Freigabe nach kombiniertem Field-Test.

**V2-Note:** Field-Test-Plan in V3 als Pflicht-Punkt.

---

## V2-Antworten auf V1's offene Fragen

1. **P1.11 Option A vs B:** A (siehe L1).
2. **P1.13 Histogramm-Update:** Vermutlich ueberfluessig im Normal-Modus
   — V3 entscheidet nach Code-Lesen ob `_freq_hist` sichtbar (siehe L3).
3. **P1.7 5-Min-Window:** 300s hardcoded, KISS (siehe L8).
4. **P1.7 Antennen-Stats:** Auch skippen (siehe L4).
5. **P1.7 Test-Zahl:** Aufstockung auf 15 Tests (siehe L11).

---

## V2-Schaerfungen fuer V3

| Punkt | V1 | V2 |
|---|---|---|
| P1.11 Counter | „Option A oder B" | Option A definitiv |
| P1.13 Hardware-Range | hardcoded 150/2800 | aus Spinbox-Properties |
| P1.13 Histogramm-Update | unbedingt | bedingt — V3 prueft |
| P1.7 Cache-Key | `call: str` | `(call, band): tuple` |
| P1.7 Antennen-Stats | offen | auch skippen |
| Test-Zahl | 11 | 15 |
| Tests-Erwartung | 949 | **953** |
| Field-Test-Plan | nicht erwaehnt | Pflicht in V3 |

---

## V3-Pflicht-Punkte

V3 muss enthalten:
- ALLE Diffs konkret (Compact-fest) mit Datei:Zeile
- Implementations-Reihenfolge mit git-add-p Hinweis
- 15 Tests konkret
- Field-Test-Pflicht-Block
- APP_VERSION 0.95.18 → 0.95.19
- Lessons-Learned-Vorschlaege

---

**V2-Ende. R1-Plan-Review folgt.**
