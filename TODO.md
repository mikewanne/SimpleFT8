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

## Vorbereitet — noch deaktiviert (12.04.2026, ergänzt 12.04.2026)

### OMNI-TX v3.2 (`core/omni_tx.py`)
**Status:** Skeleton fertig, `active = False` — Aktivierung nur via Easter Egg

**Was es tut:**
- CQ auf Even UND Odd → ~20-30% mehr Antworten auf belebten Bändern
- 5-Slot-Muster: TX TX RX RX RX (40% Sendeanteil vs. 50% normal → 20% weniger TX!)
- Block-Wechsel nach `diversity_operate_cycles // 2` Zyklen (default: 40)
- Easter Egg: Klick auf "SimpleFT8 v0.23" in GUI → Aktivierungsdialog → Ω-Symbol
- Statusbar zeigt "Ω" wenn aktiv

**Was fehlt bis zum Scharfschalten:**
- [ ] Hook in `_on_cycle_decoded`: `if cq_active and not omni_tx.should_tx(): skip_tx()`
- [ ] `omni_tx.advance(qso_active=...)` pro Zyklus aufrufen
- [ ] `omni_tx.on_qso_started()` bei QSO-Beginn aufrufen
- [ ] Feldtest: funktioniert Timing sauber? Keine Kollisionen mit laufendem QSO?

**⚠️ QSO-Schutz PFLICHT:** `should_tx()` darf nur wirken wenn `cq_active=True`!
  → Bei laufendem QSO (`qso_sm.is_busy()`) IMMER senden, nie unterdrücken.
  → Sonst bricht OMNI-TX ein laufendes QSO ab. Hook in `main_window.py` entsprechend bauen!

**Bugfix (12.04.2026):** `_switch_block()` hatte Mid-Pattern TX-Jump Bug.
  → Korrigiert: Block-Wechsel nur an Muster-Grenze (`_slot_index == 0`).
  → Wenn Zähler voll läuft, aber gerade Pos 2-4 aktiv → Wechsel verzögert bis Pos 0.

### Propagation-Balken (`core/propagation.py`)
**Status:** Implementiert und aktiv (kein Feature-Flag nötig, rein visuell)

**Was es tut:**
- 4px Farbbalken unter jedem Bandbutton (good=grün, fair=gelb, poor=rot, grey=grau)
- HamQSL XML alle 3h im Hintergrund-Thread (kein API-Key)
- Tageszeit-Korrektur: bandspezifische UTC-Fenster senken Bewertung in Übergangsstunden
- Bei Netzwerkfehler: Balken unsichtbar + einmalige Infobox

**Im Feldtest prüfen:**
- [ ] Balken erscheinen nach ~3s App-Start?
- [ ] Farben stimmen mit eigener Band-Erfahrung überein?
- [ ] Tageszeit-Korrektur plausibel? (80m mittags = rot?)

---

## Vorbereitet — noch deaktiviert (12.04.2026)

### AP-Lite v2.2 (`core/ap_lite.py`)
**Status:** Code-Skeleton fertig, `AP_LITE_ENABLED = False` — scharfschalten erst nach Feldtest!

**Was es tut:**
- Speichert PCM-Buffer wenn Decode fehlschlägt (aber Nachricht erwartet wurde)
- Gegenstation wiederholt → 2. Slot fehlschlägt → Costas-Alignment + kohärente Addition
- ~4-5 dB SNR-Gewinn durch Combining zweier Rausch-Samples
- Kandidaten aus QSO-State: State1=Reports, State2=RR73/73/RRR
- Gewichtete Korrelation → Score ≥ 0.75 → QSO retten

**Was fehlt bis zum Aktivieren:**
- [ ] `correlate_candidate()` — Encoder-Integration (Referenz-Welle aus FT8-String)
- [ ] Hook in `main_window.py`: `ap_lite.on_decode_failed()` wenn QSO aktiv + leer
- [ ] Hook in `main_window.py`: `ap_lite.try_rescue()` beim zweiten Fehler
- [ ] Encoder: `generate_reference_wave(msg, freq_hz, sample_rate)` Methode ergänzen
- [ ] Threshold 0.75 im Feldtest kalibrieren
- [ ] State-3-Kandidaten (CQ_WAIT) — Locator der Gegenstation aus Decoded-History?

**Schätzung:** 85-90% der doppelt-wiederholten QSOs gerettet = +~5% mehr QSOs

---

## Neu implementiert — Feldtest ausständig (12.04.2026)

### DT-basierte Zeitkorrektur (`core/ntp_time.py`)
**Status:** Code fertig, UNGETESTET — nur mit echtem Bandverkehr validierbar

**Was es tut:**
- Nach jedem Dekodier-Zyklus: Median aller DT-Werte berechnen
- Smoothing: 70% alter Wert + 30% neuer Median
- `FT8Timer.utc_now()` verwendet korrigierte Zeit automatisch
- Kein Internet/NTP nötig, inkludiert Radio-Latenz

**Was im Feldtest prüfen:**
- [ ] Vorzeichen korrekt? (positiver Median → Uhr geht nach → positive Korrektur)
- [ ] Smoothing-Faktor 0.3 sinnvoll? (evtl. anpassen)
- [ ] Mindestens 5 Stationen ausreichend? (bei wenig Bandverkehr)
- [ ] 50ms Deadband OK? (unter 50ms kein Korrektur)
- [ ] Log-Output prüfen: `[DT-Korr] Median=+0.XXXs → Korrektur=+0.XXXs (n=XX)`
- [ ] PSKReporter DT-Werte vorher/nachher vergleichen

**Bugfix (12.04.2026):** `update_from_decoded()` war nicht thread-sicher.
  → Korrigiert: `threading.Lock()` + `with _lock:` schützt alle State-Mutations.

**Relevante Dateien:** `core/ntp_time.py`, `core/timing.py`, `ui/main_window.py`

---

## Ideen / Später
- [ ] Turbo FT8: "Listen-Slot" — einen TX-Slot überspringen um zweiten Caller zu erfassen
  - A hört EVEN-CQ → antwortet ODD → wir TX EVEN
  - B hört ODD-CQ → antwortet EVEN → wir müssen einen EVEN-Slot freihalten zum lauschen
  - Risiko gering: WSJT-X wiederholt 5-7x automatisch
