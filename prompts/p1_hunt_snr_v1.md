# P1.HUNT-SNR — V1 (Diagnose + Plan-Entwurf)

**Status:** V1 (initial draft, Mike-Field-Test 08.05.2026 v0.95.20).
**Autor:** Claude (mit Mike-Beobachtung).
**Folge-Bug zu P1.8 (v0.95.18) — Hunt-Pfad wurde damals explizit ausgelassen.**

---

## 1. Field-Test-Beweis (Mike, 13:57 UTC, 08.05.2026)

Screenshot zeigt:

| Station    | dB  | Slot |
|------------|-----|------|
| EV81OB     | -15 | E    |
| **EV81AB** | **-18** | **E** ← Mike klickt hier |
| LZ81ZZ     | -23 | E    |

App sendet: `Sende EV81AB DA1MHH -24 (ANT1)`.

**Diskrepanz:** -18 dB empfangen, -24 dB gesendet → **6 dB falsch**.

Mike's Worte: „den wsendlich besser als das wir seinen raport senden. 6
db unterschied." → der Hunt-Report ist 6 dB schlechter als die echte
Empfangsqualitaet, weil eine andere Station im selben Slot dominanter
durch `_last_snr` ging.

Wahrscheinliche Ursache: Decoder iteriert pro Slot mehrere Messages
(EV81OB -15, EV81AB -18, LZ81ZZ -23). `_last_snr` wird in
`mw_cycle.py:805` `set_last_snr(msg.snr)` pro Message ueberschrieben.
Beim Klick auf EV81AB liest `start_qso` den Wert der zuletzt-iterierten
Station (vermutlich LZ81ZZ -23 oder ein anderer schwacher Decode -24).

---

## 2. Bug-Wurzel (Code-Verifikation 08.05.2026)

### W1 — `core/qso_state.py:276` in `start_qso(their_call, their_grid, freq_hz)`

```python
report = f"{self._last_snr:+03d}" if self._last_snr > -30 else "-10"
self.qso.our_snr = report
msg = f"{their_call} {self.my_call} {report}"
```

`self._last_snr` ist nicht station-spezifisch — wird vom Decoder pro
decodierter Message ueberschrieben. Bei Hunt-Klick auf eine spezifische
Station gewinnt aber jene, die im Decoder-Iterator ganz hinten stand.

### W2 — `ui/mw_cycle.py:562` `_run_auto_hunt`

Auto-Hunt ruft denselben `start_qso(their_call, their_grid, freq_hz)`
**ohne SNR-Parameter** → gleicher Bug.

### W3 — Vorhanden, aber kein eigener Bug: Retry-Pfade

`qso_state.py` 368, 593, 602, 653 lesen `self.qso.our_snr or
f"R{self._last_snr:+03d}"`. `our_snr` wird in `start_qso` Z.277 sofort
gesetzt — `_last_snr`-Fallback praktisch nie aktiv. ABER: wenn `our_snr`
in `start_qso` mit FALSCHEM Wert gesetzt wurde, sendet jeder Retry den
gleichen falschen Report. Folge-Risiko, kein eigenstaendiger Bug.

### W4 — P1.8-Fix in v0.95.18 war unvollstaendig

HISTORY-Zitat: „Hunt-Pfad (`start_qso`) + Retry-Pfade (Z.345,360,585,
594,642) BLEIBEN mit `_last_snr` (Fallback bekannt akzeptiert)."

Damals war die Annahme: bei Hunt-Klick ist die geklickte Station typisch
die staerkste, also `_last_snr` ≈ richtig. Mike's Screenshot widerlegt
das fuer Mehrfach-Decode-Slots (3+ Stationen).

---

## 3. Fix-Konzept (V1, KISS)

**Option A — `start_qso` Signatur erweitern (bevorzugt):**

```python
# core/qso_state.py
def start_qso(self, their_call: str, their_grid: str = "",
              freq_hz: int = 0, their_snr: int | None = None):
    ...
    # Snr-Quelle: explizit > _last_snr-Fallback
    snr = their_snr if their_snr is not None else self._last_snr
    report = f"{snr:+03d}" if snr > -30 else "-10"
    self.qso.our_snr = report
    ...
```

Aufrufer:

```python
# ui/mw_qso.py:138
self.qso_sm.start_qso(
    their_call=msg.caller,
    their_grid=msg.grid_or_report if msg.is_grid else "",
    freq_hz=msg.freq_hz,
    their_snr=msg.snr,  # P1.HUNT-SNR (v0.95.21)
)

# ui/mw_cycle.py:562
self.qso_sm.start_qso(
    their_call=_candidate.call,
    their_grid=_candidate.grid,
    freq_hz=_candidate.freq_hz,
    their_snr=getattr(_candidate, 'snr', None),  # falls AutoHuntCandidate snr hat
)
```

**Backward-Compat:** Default `None` → fallback `_last_snr`. Tests die
`start_qso(...)` ohne SNR rufen brauchen keine Anpassung.

**Auto-Hunt-Vorbedingung:** `core/auto_hunt.py` `AutoHuntCandidate` muss
ein `snr`-Feld haben (vermutlich nicht — Verifikation in V2 noetig).
Falls nicht: Feld hinzufuegen + `select_next` snr aus FT8Message
durchreichen.

---

## 4. Akzeptanzkriterien (10 ACs)

1. ✅ Hunt-Klick auf Station mit SNR=X → erster TX-Frame zeigt SNR=X
   (nicht `_last_snr`).
2. ✅ Auto-Hunt waehlt Candidate mit SNR=X → erster TX-Frame zeigt SNR=X.
3. ✅ Backward-compat: alte Tests die `start_qso(call, grid, freq)`
   ohne SNR rufen, laufen weiter (fallback auf `_last_snr`).
4. ✅ Mike's Slot-Szenario (3 Stationen verschieden SNR) → Report ist
   station-spezifisch korrekt.
5. ✅ `our_snr` im `QSOData`-Objekt enthaelt den korrekten Report
   (Retry-Pfade lesen das, kein Folge-Bug).
6. ✅ Edge-Case: `their_snr = None` (Auto-Hunt mit alter Candidate-
   Struktur ohne snr-Feld) → graceful fallback auf `_last_snr`.
7. ✅ Edge-Case: `their_snr = -99` (sehr schwacher Decode) → wird auf
   "-10" geclamped (gleiches Verhalten wie heute mit `_last_snr <= -30`).
8. ✅ APP_VERSION 0.95.20 → 0.95.21.
9. ✅ Tests 992 → ~999 (geschaetzt +6: 1 Hunt-Klick + 1 Auto-Hunt + 1
   Backward-compat + 1 Edge-Case + 1 Multi-Decode-Slot + 1 our_snr-
   Persistenz).
10. ✅ Final-R1 ohne KRITISCH/SOLLTE-Findings.

---

## 5. Offene Fragen (an V2-Self-Review)

1. **Hat `AutoHuntCandidate` ein `snr`-Feld?** Wenn nein: Feld
   hinzufuegen — Datenfluss `select_next` → Candidate-Konstruktor.
2. **Wird `_run_auto_hunt`-Pfad ueberhaupt von Mike genutzt?** Falls
   selten: niedrigere Prio, kann in V3 als Followup verschoben werden.
3. **Pfad fuer CQ-Antwort beim CQ-Modus** (`_process_cq_reply` schon
   gefixt in v0.95.18) — aber gibt es einen anderen Pfad wo eine CQ-
   Antwort auf eine CQ ausserhalb `_process_cq_reply` landet? V2 muss
   grep auf `start_qso` machen.
4. **Existiert ein QSO-Panel-Display fuer „SNR die wir senden"?** Falls
   ja: muss der gleiche Wert kommen.
5. **Was passiert wenn Klick im IDLE-Slot ohne Decode davor?**
   `_last_snr=−10` Default — aber dann gibt es auch keine `msg`-Quelle.
   Edge-Case nur fuer Tests relevant.
6. **Tests die NEU sind: brauchen Qt-offscreen?** Fuer reine
   `start_qso`-Aufrufe nein, fuer mw_qso-Integration ja.
7. **Doppel-Fix-Zone:** sind RX-Panel `dB`-Spalte + Logbuch ADIF
   `<RST_SENT>` betroffen? Logbuch holt `our_snr` aus QSO-Data, also
   ja — wird durch Bug-Fix automatisch korrekt.

---

## 6. Risiken

- **Test-Bruch bei Backward-compat-Tests:** kontern via Default-None.
- **Auto-Hunt ohne snr-Feld am Candidate:** graceful fallback auf
  `_last_snr` — bestehender Bug bleibt aber im Auto-Hunt-Pfad falls
  Candidate-Struktur nicht erweitert wird. V2 entscheidet Scope.
- **CQ-Reply-Pfad (`_process_cq_reply`)** ist NICHT betroffen — schon
  gefixt in v0.95.18. Verifikation in V2: keine Doppel-Pfade.

---

## 7. Workflow-Plan

V1 (diese Datei) → V2 (Self-Review, Code-Verifikation der offenen
Fragen) → R1 (DeepSeek-Reasoner Plan-Review) → V3 (Compact-fest) →
Compact → Code → Final-R1 → 2 atomare Commits + Doku.

**Erwartung:** 1-2 Stunden Workflow + Code, ~10 Zeilen Diff Hauptbug,
+ ~5-10 Zeilen wenn AutoHuntCandidate-snr ergaenzt werden muss.
