# P1.HUNT-SNR — V2 (Self-Review)

**Status:** V2 (Self-Review nach V1, Code-Verifikation aller offenen Fragen).
**Folge zu V1.** Mike-Field-Test 08.05.2026, Folgebug zu P1.8 (v0.95.18).

---

## V1 → V2 Aenderungen

V1 hatte 7 offene Fragen. V2 hat alle via grep + Read verifiziert.
Ergebnis: Plan ist enger als V1 dachte.

### Antworten auf V1-Fragen (Code-Verifikation)

**Q1: Hat `AutoHuntCandidate` ein `snr`-Feld?**
✅ JA. `core/auto_hunt.py:53-57`:
```python
@dataclass
class _HuntCandidate:
    call: str
    grid: str
    freq_hz: int
    tx_even: bool | None
    snr: int
```
`snr=msg.snr if msg.snr is not None else -30` (Z.227). Direkt nutzbar.

**Q2: Wird `_run_auto_hunt`-Pfad genutzt?**
✅ JA. Mike hat `auto_hunt`-Logik produktiv. Beide Pfade muessen
gefixt werden, kein Followup-Verschieben.

**Q3: Andere Pfade wo CQ-Antwort ausserhalb `_process_cq_reply` landet?**
✅ NEIN. grep auf `qso_sm.start_qso` ergibt nur 2 produktive Aufrufer:
- `ui/mw_qso.py:138` (Hunt-Klick durch User)
- `ui/mw_cycle.py:562` (Auto-Hunt automatisch)
Alle anderen Treffer sind in `Appsicherungen/` (alte Backups). CQ-Reply
laeuft komplett separat in `_process_cq_reply` (qso_state.py:200ff) —
bereits in v0.95.18 mit `msg.snr` gefixt.

**Q4: Existiert ein QSO-Panel-Display fuer „SNR die wir senden"?**
✅ JA — `ui/qso_panel.py` zeigt TX-Messages 1:1 wie sie gesendet werden
(uebernimmt aus `tx_started.emit(msg, ...)`-Signal). Nach Fix wird
automatisch der korrekte SNR angezeigt — kein separater Pfad.

**Q5: Klick im IDLE-Slot ohne Decode davor?**
Nicht praxisrelevant — ein Klick passiert IMMER auf eine Message in
RX-Panel, die eine `msg.snr` hat. Edge-Case nur fuer Tests
(`start_qso(call, grid, freq)` ohne `their_snr`) — Backward-compat
fallback auf `_last_snr`.

**Q6: Tests die Qt-offscreen brauchen?**
- Reine `start_qso(...)`-Tests (qso_state.py): KEIN Qt noetig.
- Hunt-Klick-Integration (mw_qso): Qt-offscreen.
- Auto-Hunt-Integration (mw_cycle): Qt-offscreen.

**Q7: Doppel-Fix-Zone RX-Panel + Logbuch ADIF?**
- RX-Panel `dB`-Spalte zeigt EMPFANGS-SNR der Gegenstation, nicht
  unseren TX-Report. NICHT betroffen.
- Logbuch ADIF `<RST_SENT>` holt aus `qso.our_snr` — wird durch Fix
  automatisch korrekt (Hauptbug-Fix setzt `our_snr` korrekt in
  `start_qso`).

---

## Lessons L1-L12 (Self-Review)

### L1 — `_HuntCandidate.snr` existiert bereits
V1 vermutete „Feld muss neu hinzugefuegt werden" — ist schon da. **Plan
schlaegt Cliff: keine zusaetzliche Auto-Hunt-Refaktorierung noetig.**
Nur `their_snr=_candidate.snr` in `mw_cycle.py:562` durchreichen.

### L2 — Nur 2 produktive Aufrufer
Reduziert Risiko von vergessenen Stellen drastisch. **Die 2 Aufrufer
sind die einzigen Code-Pfade, die wir aendern muessen.**

### L3 — Backward-compat zwingend wegen bestehenden Tests
grep auf `start_qso(` in `tests/`:
```
tests/test_qso_state.py: viele Aufrufe
tests/test_p1_14_*.py: einige
tests/test_p1_24_*.py: einige
```
**Konsequenz:** `their_snr: int | None = None` Default ist Pflicht. KEIN
Breaking-Change.

### L4 — V1 Option A ist KISS, keine Alternative noetig
Option B (komplett ohne `_last_snr` arbeiten) waere Overengineering — `_last_snr`
hat noch Verwendung in:
- `qso_state.py:368` Retry WAIT_REPORT (`our_snr`-Fallback)
- `qso_state.py:593, 602` Retry WAIT_RR73 (`our_snr`-Fallback)
- `qso_state.py:653` Counter-Inkrement (`our_snr`-Fallback)
- `qso_state.py:280` Debug-Log
- `mw_cycle.py:538` AP-Lite snr_estimate
- `ui/mw_qso.py:738` Bandpilot-Display

Diese alle anfassen waere Risiko ohne Nutzwert (Retry liest `qso.our_snr`
das nach Fix korrekt ist).

### L5 — Test-Skeleton
Neue Tests in `tests/test_p1_hunt_snr.py`:
1. `test_start_qso_uses_their_snr_when_provided` — explicit `their_snr=-18`
   → `our_snr == "-18"`
2. `test_start_qso_falls_back_to_last_snr_when_none` — `their_snr=None`
   → liest `_last_snr` (backward-compat)
3. `test_start_qso_clamps_weak_snr` — `their_snr=-99` → `"-10"` (gleich
   wie `_last_snr <= -30` Logik)
4. `test_start_qso_sends_correct_msg_text` — assertion auf
   `send_message`-Signal-Argument
5. `test_hunt_click_passes_msg_snr_to_start_qso` (mw_qso, Qt-offscreen)
6. `test_auto_hunt_passes_candidate_snr_to_start_qso` (mw_cycle,
   Qt-offscreen)
7. `test_multi_decode_slot_uses_clicked_station_snr` — Slot mit 3
   Stationen verschieden SNR, Klick auf mittlere → Report ist mittlere
8. `test_our_snr_persisted_in_qso_data` — `qso.our_snr` enthaelt
   korrekten Wert nach `start_qso`

**Plus:** Bestehende Tests die `start_qso(call, grid, freq)` ohne SNR
rufen, **muessen weiter gruen sein** ohne Anpassung — Backward-compat-Beweis.

### L6 — Edge-Case `their_snr=0`
`their_snr is not None` ist robust gegen `0` (waere mit `if their_snr:`
ein Bug). V3 bestaetigt diese Form.

### L7 — `_last_snr=−10` Default und `> -30`-Schwelle
Aktuell: `> -30` → Report wird gesendet, sonst „-10". Bei `their_snr`
gleiche Logik wahren. Edge-Case-Test (L5 #3) sichert es.

### L8 — `our_snr`-Format „Hunt" vs „CQ-Reply"
- Hunt (`start_qso`): Erste TX-Frame ist Report ohne R-Praefix.
  `report = f"{snr:+03d}"` (zb. "-18").
- CQ-Reply (`_process_cq_reply`): Erste TX-Frame haengt von `is_grid`
  vs `is_report` ab. Bei `is_grid` Z.220: `report = f"{snr:+03d}"` (zb.
  "-18"). Bei `is_report+is_r_report` → RR73 (kein Report). Bei
  `is_report+nicht-r` → R-prefix `f"R{snr:+03d}"` (zb. "R-18").

Hunt-Pfad nutzt KEINE R-Praefix-Variante. Logik symmetrisch zum
`is_grid`-Pfad in `_process_cq_reply`. Konsistent.

### L9 — KEIN APP_VERSION-Aenderungs-Bedarf-Risiko
Das ist ein Bug-Fix, kein Feature → APP_VERSION 0.95.20 → 0.95.21.

### L10 — `_run_auto_hunt`: getattr-Schutz oder Direkt-Zugriff?
Da `_HuntCandidate.snr: int` ein Pflichtfeld in der dataclass ist, kann
direkt `_candidate.snr` genutzt werden — kein `getattr(_candidate, 'snr',
None)` noetig. V1's Vorsicht war ueberzogen. V3 nutzt direkten Zugriff.

### L11 — Tests-Soll: 992 → 1000 (+8)
V1 schaetzte +6, V2 plant +8 (`test_p1_hunt_snr.py` mit 8 Tests aus L5).

### L12 — Doku-Zone
- HISTORY: neuer v0.95.21-Block oberhalb v0.95.20.
- HANDOFF (beide Pfade): aktueller Stand.
- CLAUDE.md (beide Pfade): Aktueller Stand-Block + Test-Count.
- TODO: kein neuer Punkt — Bug ist Folge von P1.8, nicht im Backlog.
- Memory: ✅-Eintrag + ggf. Lesson „Hunt-Pfad bei P1.X-Bug-Fixes mit-
  pruefen" (`feedback_partial_fix_check_other_paths.md`).

---

## V2-Diff zu V1 — was bleibt, was aendert sich

| V1 | V2 |
|---|---|
| 5 ACs explizit + 5 implizit | 8 strukturierte ACs (L5) + Backward-compat-AC |
| `getattr(_candidate, 'snr', None)` | direkt `_candidate.snr` (L10) |
| AutoHuntCandidate-Refactor evtl. | NICHT noetig — Feld existiert (L1) |
| Test-Soll +6 | +8 (L11) |
| 7 offene Fragen | alle 7 beantwortet |
| Plan ~10-15 Zeilen Diff | Plan ~10 Zeilen Diff (Auto-Hunt-Refactor wegfaellt) |

---

## V2-finaler Plan (vor R1-Review)

### Diff 1 — `core/qso_state.py` `start_qso()` Signatur + Body

```python
def start_qso(self, their_call: str, their_grid: str = "",
              freq_hz: int = 0, their_snr: int | None = None):
    """QSO mit angeklickter Station starten. Bricht laufendes QSO ab.

    P1.HUNT-SNR (v0.95.21): their_snr ist station-spezifischer SNR
    aus FT8Message — verhindert dass _last_snr (vom letzten Decoder-
    Iterator-Schritt im Slot) den Report dominiert. Backward-compat:
    None → fallback auf _last_snr (alte Tests).
    """
    # ... bestehender Reset-Code unveraendert ...

    self._was_cq = self.cq_mode

    self.qso = QSOData(...)

    self._dbg.reset(their_call)
    # P1.HUNT-SNR (v0.95.21): explizite their_snr > _last_snr-Fallback
    snr = their_snr if their_snr is not None else self._last_snr
    report = f"{snr:+03d}" if snr > -30 else "-10"
    self.qso.our_snr = report
    msg = f"{their_call} {self.my_call} {report}"
    self._dbg.log("START", f"Hunt: {their_call} auf {freq_hz}Hz, ...")
    self._dbg.log("TX", f"Sende: '{msg}' (SNR={snr})")
    self._set_state(QSOState.TX_CALL)
    self.send_message.emit(msg)
```

### Diff 2 — `ui/mw_qso.py:138` Hunt-Klick

```python
self.qso_sm.start_qso(
    their_call=msg.caller,
    their_grid=msg.grid_or_report if msg.is_grid else "",
    freq_hz=msg.freq_hz,
    their_snr=msg.snr,  # P1.HUNT-SNR (v0.95.21)
)
```

### Diff 3 — `ui/mw_cycle.py:562` Auto-Hunt

```python
self.qso_sm.start_qso(
    their_call=_candidate.call,
    their_grid=_candidate.grid,
    freq_hz=_candidate.freq_hz,
    their_snr=_candidate.snr,  # P1.HUNT-SNR (v0.95.21)
)
```

### Diff 4 — `main.py` APP_VERSION

```python
APP_VERSION = "0.95.21"
```

### Diff 5 — NEU `tests/test_p1_hunt_snr.py` (8 Tests)

Aus L5 abgeleitet.

---

## Risiken

- **Test-Bruch bei alten Backward-compat-Tests:** kontern via Default-None.
  Verifikation: kein bestehender Test sollte Fehler werfen.
- **Folge-QSO-Pfade:** `our_snr` wird in `start_qso` korrekt gesetzt —
  alle Retry-Pfade lesen `our_snr` zuerst, fallback `_last_snr` nur als
  Sicherheitsnetz. Kein Sekundaer-Fix noetig.
- **Auto-Hunt-Test-Coverage:** existierende Auto-Hunt-Tests pruefen
  nicht den SNR-Pfad. Neuer Test (L5 #6) erforderlich.

---

## R1-Pruefauftraege (8)

R1-Plan-Review soll explizit pruefen:

1. **Pull-Pattern-Konsistenz:** `their_snr` aus FT8Message ist Push,
   nicht Pull. Akzeptabel? (Antenne via Pull war P3-Pattern, hier ist
   Datenfluss umgekehrt: Aufrufer kennt `msg.snr` direkt, kein Buffer
   noetig.)
2. **Race in `_process_cq_reply`:** wir aendern den NICHT, ist das
   konsistent? (Ja, weil dort schon `msg.snr` direkt benutzt wird —
   v0.95.18 P1.8.)
3. **Auto-Hunt-Candidate-Snr-Default:** in `auto_hunt.py:227` wird
   `snr=msg.snr if msg.snr is not None else -30` als Fallback gesetzt.
   Wenn `_candidate.snr=-30` an `start_qso(their_snr=-30)` durchgereicht
   wird, kommt Report „-30" raus statt „-10" (Schwelle ist `> -30`).
   **Pruefen ob das ein Bug oder gewollt ist.**
4. **Schwelle „> -30":** Mike's Empfangs-Praxis — erlaubt FT8 Reports
   bis -30? WSJT-X-Default ist „-10" als Untergrenze. Verifizieren.
5. **Backward-compat-Test-Liste:** existieren Tests die genau die Werte
   pruefen die wir aendern wollen?
6. **`_last_snr`-Default −10 wird ungenutzt nach Fix?** Nein — fallback
   bleibt aktiv fuer Tests + Edge-Cases. Akzeptabel?
7. **Logbuch-ADIF-Konsistenz:** `<RST_SENT>` ist `our_snr` aus QSOData.
   Field-Test-fertig oder eigener Test noetig?
8. **Field-Test-Plan:** klare Reproduktion (Slot mit 3+ Stationen,
   Klick auf mittlere SNR-Station, Vergleich Empfangs-SNR vs
   gesendeter Report).

---

**V2-Ende. Bereit fuer R1-Plan-Review (DeepSeek-Reasoner).**
