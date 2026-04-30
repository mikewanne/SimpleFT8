# Timing-Bug Diagnose + Test-Plan — 2026-05-01

## Problem

QSO-Regression seit 27.04.2026 (vorher 20+ erfolgreiche QSOs).
Symptom: Report `-23` von Mike's Flex kommt bei DA1TST (Icom direkt
nebenan, Dummy-Load) nicht an. Drei Retries, dann Timeout. Nach
Timeout sofort wieder Antwort-Versuch — Endlos-Schleife.

Mike's Beobachtung: Icom zeigt **DT 0.0** bei Mike's Sendung, also
TX-Sync ist OK. Trotzdem decodet das Icom den Report nicht.

## R1-Diagnose (Sonderbar)

| Rang | Hypothese | Wahrscheinlichkeit |
|---|---|---|
| 1 | **A/D — ANT1-Hook stoert TX-Sequenzierung** (commit `fac60a0` v0.75) | **~90%** |
| 2 | C — `dt_corrections.json` zeigt FT8_20m=0.65s (erwartet ~0.24s) | sekundaer |
| 3 | B — Decode-Latenz 5-Pass blockiert TX-Decision | nicht primaer |
| — | E — `txant=ANT1` koennte auf Flex-Modell ungueltig sein | unbekannt |

### Code-Stelle (`core/encoder.py:233-236`)

```python
# 6. PTT an — Stille gibt 0.3-0.5s PTT-Settle-Zeit
if self._radio:
    self._radio.set_tx_antenna("ANT1")  # NEU seit v0.75 commit fac60a0
    self._radio.ptt_on()
```

`set_tx_antenna()` ist **fire-and-forget** TCP-Befehl. `ptt_on()`
gleich danach. FlexRadio koennte `xmit 1` verarbeiten BEVOR `txant`
gesetzt ist (Race) oder `set_tx_antenna` schaltet das Antennen-Relais
(~10-50ms) und verzoegert/stoert TX-Sequencing.

→ Audio-Pakete koennten ankommen bevor TX-Pfad konfiguriert ist —
   Empfaenger sieht degradiertes oder verstuemmeltes Signal.

## Setup (Mike)

- **Mike's Flex** sendet (ANT1 = Kelemen-Trap-Dipol oder direkt Dummy)
- **Mike's Icom 705** als FT8-Empfaenger nebenan, Dummy-Load
- Icom auf **feste Frequenz 14.074 MHz**, feste RX-Antenne
- App **NICHT** waehrend Tests Frequenz/Modus aendern (DT-Korrektur stabil halten)

## Test-Plan (priorisiert)

### Test 1 — Baseline reproduzieren (5 Min)

**Setup:** v0.78 unveraendert (HEAD `db10b2d`).

**Durchfuehrung:**
1. App starten
2. CQ-Modus aktivieren, 10 CQ-Slots am Stueck senden lassen
3. Icom: Decode-Anzeige beobachten — wieviele Slots werden dekodiert?

**Erwartung:** Decode-Rate < 30% bei DA1TST.

**Notieren:**
- Anzahl dekodierter CQ-Slots / 10
- DT-Anzeige am Icom (sollte ~0.0s sein)
- Mike's Flex SNR-Anzeige fuer DA1TST

→ Wenn das Problem reproduzierbar ist, weiter zu Test 2.

---

### Test 2 — ANT1-Hook entfernen (Hauptverdacht, 30 Min)

**Patch:**

```python
# core/encoder.py Z.233-236 — ANT1-Hook auskommentieren:
# 6. PTT an — Stille gibt 0.3-0.5s PTT-Settle-Zeit
if self._radio:
    # self._radio.set_tx_antenna("ANT1")  # disabled fuer Test
    self._radio.ptt_on()
```

**Durchfuehrung:**
1. Patch anwenden
2. App starten
3. **Im FlexRadio-CAT-Logfile manuell verifizieren:** ist `txant=ANT1`
   gesetzt? (Sollte beim letzten Connect persistent sein)
4. CQ-Modus, 10 CQ-Slots
5. Icom: Decode-Rate?

**Erwartung:** Decode-Rate steigt auf >90%, Report kommt durch,
QSO komplett. → Hauptursache bestaetigt.

**Wichtig:** Diese Aenderung ist NUR fuer Test. Wenn Test 2 erfolgreich,
machen wir die saubere Loesung in Test 5: einmalig in `connect()` oder
`_start_radio()`.

---

### Test 3 — DT-Korrektur reset (15 Min)

**Patch:**

```bash
# DT-Korrektur loeschen — App muss neu konvergieren
mv ~/.simpleft8/dt_corrections.json ~/.simpleft8/dt_corrections.json.bak
```

**Durchfuehrung:**
1. Test 2-Patch anwenden ODER zurueck auf Baseline
2. App starten
3. 30 Min RX laufen lassen → DT-Korrektur sollte sich auf ~0.24s einpendeln
4. `cat ~/.simpleft8/dt_corrections.json` pruefen

**Erwartung:** FT8_20m konvergiert auf ~0.24s. Falls Test 2 nicht
geholfen hat, koennte falsche DT-Korrektur Mitverursacher sein.

---

### Test 4 — Decoder-Pass-Reduktion (optional, 10 Min)

Nur wenn Test 2 + 3 nicht ausreichen.

**Patch:**

```python
# core/decoder.py — MAX_SUBTRACT_PASSES suchen, 5 → 3
```

**Erwartung:** Schnellere Decode-Latenz, ggf. weniger schwache
Stationen empfangen aber TX-Decision-Window groesser.

---

### Test 5 — Saubere Loesung (nach Test 2 Erfolg)

**Endgueltiger Fix:**

```python
# core/encoder.py:233-236 — ANT1-Hook entfernen, ZURUECK auf v0.74-State

# core/flexradio.py oder mw_radio.py: einmalig nach connect()
def connect(...):
    ...  # bisheriger Connect-Code
    self.set_tx_antenna("ANT1")  # einmal beim Start, dann nie wieder im TX-Path
```

ANT1-Pflicht bleibt erhalten:
- ✅ Beim Connect gesetzt (einmalig)
- ✅ Bei jedem TUNE explizit gesetzt (`mw_tx.py:83`, bleibt)
- ✅ Bei `_enable_diversity()` und `_disable_diversity()` (bestehend)
- ✅ Bei `dx_tune_dialog.py` Mess-Pipeline (bestehend)
- ❌ NICHT mehr im Hot-Path `Encoder.transmit()` (Slot-kritisch)

---

### Test 6 — Vollstaendiges QSO

Nach erfolgreichem Test 5: 5 vollstaendige QSO-Cycles
CQ → Antwort → Report → RR73 → 73 sauber durchlaufen lassen.

**Erwartung:** Alle 5 QSOs komplett, ADIF-Eintrag mit Confirmed.

---

## Zusatz-Diagnose-Checks (vor Test-Beginn, 5 Min)

```bash
# FlexRadio-Firmware-Version pruefen
grep -i "Version\|firmware" /tmp/simpleft8.log | head -3

# txant-Befehl auf Flex-Modell verifizieren
# (nur wenn bekannt: SmartSDR-API-Doku checken ob `slice set X txant=ANT1`
#  syntax stimmt — sonst stille Fehlermeldung)
```

---

## Workflow danach

Wenn Tests bestaetigen dass A/D Hauptursache:

1. **V1 → V2 → V3 Workflow** fuer den Fix (workflow v1.1)
2. Mike-Freigabe
3. Atomare Commits — `fix(encoder): ANT1-Hook aus Hot-Path entfernen + Connect-Time Anker`
4. Final-R1-Codereview
5. v0.79 Release

## App-Status

- App beendet (`PID 41627` getoetet)
- v0.78 in `main` (HEAD `db10b2d`)
- Backup `Appsicherungen/2026-04-30_vor_omni_implementierung/` (v0.77 Stand)
- 493 Tests gruen

## Wichtig fuer Mike

- **Nicht voreilig fixen** — erst Test 1 zur Reproduktion
- **Keine Frequenzwechsel** waehrend Tests (DT-Korrektur stabil)
- **Icom-Logs sammeln** — Decode-Rate, DT-Anzeige, SNR
- Test 2 ist der **kritische Test** — wenn der greift, ist die Architektur klar
