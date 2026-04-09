# SimpleFT8 TODO — Stand 08.04.2026

## Morgen früh testen (nach Neustart mit TARGET_TX_OFFSET=-0.65)

### 1. DT-Timing Test
- CQ rufen, ICOM beobachten
- Ziel: DT konstant ~+0.5s (war: -2.8 bis +1.2, fix: immer +0.8-0.9, jetzt -0.65 offset)
- Kaltstart: erster TX darf Ausreißer sein (Guard aktiv), ab zweitem stabil
- Test in Normal-Modus UND Diversity-Modus

### ~~2. CQ auf EVEN und ODD senden~~ — VERWORFEN
- Verstößt gegen FT8-Standard: Antwortende Stationen würden sich gegenseitig
  blockieren (man sieht sie nicht während man selbst TX ist → Kollisionen).
  FT8 setzt voraus dass eine Station genau einen festen Slot belegt.

### 3. Diversity-Messung FIX (WICHTIG!)
**Problem:** Nach 20 Min wird während CQ neu gemessen → unterbricht Betrieb
**Was soll raus:** Neueinmessung WÄHREND CQ (CQ_CALLING/CQ_WAIT States)

**Gewünschtes Verhalten:**
- Einmessen: NUR bei Diversity-Aktivierung + Bandwechsel
- Gültigkeit: 15 Min (nicht 20 Min) ODER bis Bandwechsel
- Re-Messung: nur wenn IDLE (nicht wenn CQ oder QSO aktiv)
- Während CQ/QSO: immer auf letztem bekanntem Ergebnis weiterarbeiten

**Code-Änderungen (core/diversity.py + ui/main_window.py):**
```python
# diversity.py: OPERATE_CYCLES von 80 → 60 (15 Min)
OPERATE_CYCLES = 60  # 15 Min

# main_window.py Zeile ~1316: CQ-States NICHT remeasuren
qso_active = self.qso_sm.state not in (
    QSOState.IDLE, QSOState.TIMEOUT,
    # CQ_CALLING und CQ_WAIT RAUS → kein Remeasure während CQ!
)
```

## Erledigte Features (09.04.2026)
- [x] CQ 60s-Bug gefixt → jetzt alle 30s (Slot-Fenster 0.5→3.0s + Kaltstart-Guard intelligent)
- [x] Diversity UX: Dialog, CQ-Sperre, NEUEINMESSUNG, Zyklen einstellbar (80/160/240)
- [x] RX-OFF Warnung in Titelleiste: "⚠ EMPFANG RX DEAKTIVIERT ⚠"
- [x] TX-Balken entfernt → "Clipschutz X%" + "TX-Pegel: X%" + "SWR X.X" als Text
- [x] TX-Zeiten im QSO-Panel auf Slot-Start gerundet
- [x] Messung pausiert bei CQ/QSO (kein Remeasure während Funkbetrieb)

## Erledigte Features (08.04.2026)
- [x] TX-Timing Jitter-Fix: Silence-Padding (war -2.8..+1.2s, jetzt stabil)
- [x] TARGET_TX_OFFSET=-0.65 für DT≈+0.5 auf ICOM (FlexRadio 0.8s Latenz kompensiert)
- [x] Kaltstart-Guard: silence<0.1s → nächsten Slot nehmen
- [x] UTC im QSO-Panel: Slot-Start zeigen statt Decode-Zeit
- [x] "Beendet ist beendet": kuerzlich gearbeitete Stationen 5 Min ignorieren

## Ideen / Später
- [ ] Turbo FT8: "Listen-Slot" — einen TX-Slot überspringen um zweiten Caller zu erfassen
  - A hört EVEN-CQ → antwortet ODD → wir TX EVEN
  - B hört ODD-CQ → antwortet EVEN → wir müssen einen EVEN-Slot freihalten zum lauschen
  - Risiko gering: WSJT-X wiederholt 5-7x automatisch
