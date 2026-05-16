# Mike's Testplan P63 — 15.05.2026 spätnachmittags
**App-Stand:** v0.97.36 · Tests **1327 grün** · Push pending bis Field-Test ✓

---

## Vorbereitung — App neu starten

```
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8" && ./venv/bin/python3 main.py
```

Versionsnummer unten rechts in Statusbar muss **0.97.36** zeigen.

---

## Was P63 fixt (kurz)

Mike-Erlebnis vom 17m-Band heute nachmittag:
- SWR-Watchdog feuerte → Modal kam → DANACH:
  - TUNE-Button gesperrt (Bug — Mike braucht aber TUNE)
  - OMNI/Hunt klickbar (würden sofort wieder SWR-Alarm geben)
- **P63 dreht das um:** SWR-Sperre = Band-Marker → OMNI/Hunt/CQ blockiert
  bis manueller TUNE durchläuft. TUNE bleibt KLICKBAR (Diagnostik).
- Neue Settings: „Antennen-Tuner verwenden" + „TUNE-Dauer 15/30s".

---

## ⭐ Block A — P63 SWR-Block per Band-Marker (10 Punkte)

### F1 — SWR-Alarm auslöst Band-Marker

1. **20m FT8** aktivieren — falls noch nicht gemacht: **Diversity Std** klicken
2. Auf **17m** wechseln (kein Preset → Auto-Gain-Mess startet mit TUNE 10W)
3. Wenn 17m-Antenne nicht resonant → SWR > 2.5 → **SWR-Watchdog feuert**

**Erwartet:**
- Modal kommt: **„Band gesperrt — SWR zu hoch"** mit Text
  „Band 17M gesperrt — SWR X.X > Limit 3.0. Bitte manuell durch
  TUNE-Vorgang freischalten."
- QSO-Panel zeigt: **„⚠ Band 17M gesperrt — SWR X.X"**

**Wenn Modal mit „Band gesperrt" → F1 ✓**

### F2 — Buttons nach Modal-OK: TUNE klickbar, OMNI/Hunt blockiert

1. Modal mit **OK** bestätigen
2. **TUNE-Button** (Hauptfenster) → klickbar (nicht ausgegraut)
3. **OMNI CQ** klicken → in QSO-Panel sollte stehen:
   „⚠ OMNI blockiert — Band 17M SWR-Sperre. Manueller TUNE zum Freischalten."
   Button geht zurück auf nicht-aktiv.
4. **AUTO HUNT** klicken → analog, gleiche Info-Meldung.

**Wenn TUNE klickbar UND OMNI/Hunt blockiert mit Info → F2 ✓**

### F3 — Manueller TUNE 15s mit 10W

1. **TUNE-Button** klicken
2. Statusbar: **„TUNEN — 10W auf ANT1 für 15s ..."**
3. Tuner stimmt ein (15s)
4. Nach 15s automatisch tune_off
5. Statusbar: **„TUNE beendet — prüfe SWR (2 s) ..."**

**Wenn TUNE mit 10W startet UND nach 15s automatisch endet → F3 ✓**

### F4 — Nach TUNE-Erfolg → Marker grün + Diversity automatisch

1. Wenn Tuner es geschafft hat (SWR < Limit) → **2s nach tune_off:**
2. QSO-Panel: **„✓ Band 17M freigegeben — SWR X.X"**
3. Diversity-Modus läuft weiter (Gain-Mess startet automatisch via
   P62-1s-Pause-Pattern)

**Wenn ✓-Eintrag UND Diversity läuft weiter → F4 ✓**

### F5 — Nach TUNE-Misserfolg → Modal „Tuner konnte nicht matchen"

1. Falls 17m wirklich tot ist (Antenne ab oder so) → SWR bleibt > Limit
2. **2s nach tune_off** → Modal: **„Tuner konnte nicht matchen"**
   mit Text „SWR weiter X.X > Limit 3.0. Antenne prüfen oder TUNE wiederholen."
3. **Marker bleibt rot** — OMNI/Hunt/CQ weiterhin blockiert.

**Wenn Modal „Tuner konnte nicht matchen" UND Marker bleibt → F5 ✓**

### F6 — Settings „Tuner = NEIN" → TUNE-Button hidden, Gain-Mess ohne Auto-TUNE

1. **Settings öffnen** → Tab **„FT8 & Diversity"**
2. **Checkbox „Antennen-Tuner verwenden"** → DEAKTIVIEREN
3. **Speichern**
4. **TUNE-Button** im Hauptfenster ist jetzt **UNSICHTBAR** (hidden)
5. Diversity-Modus auf neuem Band starten → kein TUNE, direkt Gain-Mess.

**Wenn TUNE-Button verschwunden UND kein Auto-TUNE → F6 ✓**

### F7 — Settings „Tuner = NEIN" → SWR-Alarm stoppt nur, kein Marker

1. Bei deaktiviertem Tuner: TX auf einem Band mit defekter Antenne
2. SWR-Watchdog feuert → Modal: **„SWR-Schutz ausgelöst"** mit Text
   „TX abgebrochen — SWR X.X > Limit. Antenne prüfen."
3. **KEIN Marker** wird gesetzt
4. OMNI/Hunt/CQ wieder klickbar (würden aber sofort wieder feuern bei TX)

**Wenn Modal „SWR-Schutz ausgelöst" UND OMNI/Hunt klickbar → F7 ✓**

### F8 — Settings „TUNE-Dauer 30s"

1. Tuner wieder AKTIVIEREN (für nächste Test-Schritte)
2. **TUNE-Dauer (manuell)** → **30 s** wählen
3. **Speichern**
4. Manueller TUNE klicken → Statusbar zeigt **„TUNEN — 10W auf ANT1 für 30s ..."**
5. TUNE läuft 30s (nicht 15s)

**Wenn 30s-TUNE → F8 ✓**

### F9 — Marker ist pro Band

1. 17m rot (Marker gesetzt)
2. Auf **20m** wechseln
3. Auf 20m sollte alles **normal** laufen — OMNI/Hunt klickbar, kein Block.

**Wenn 20m normal läuft trotz 17m rot → F9 ✓**

### F10 — App-Restart → alle Marker weg

1. App neu starten
2. Auf 17m wechseln — Marker ist **NICHT** mehr da
3. Diversity startet normal (Gain-Mess via P62-1s-Pause)

**Wenn nach Restart kein Marker → F10 ✓**

---

## Block B — Regressions-Checks (alte Bundles weiterhin OK)

### B1 — P62 Bandwechsel-UX-Pause

- Bandwechsel auf neues Band ohne Preset → 1s Pause „TX gestoppt —
  Gain-Messung startet in 1s ..." sichtbar.

### B2 — P61 Recent-QSO-Cooldown

- Auto-Hunt-QSO mit Station X → Auto-Hunt picked nächstes Mal andere
  Station, nicht X.

### B3 — Bundle K CQ-Button-Grün

- Normal-CQ klicken → Button grün. OMNI/Hunt analog.

### B4 — Bundle K SWR-Combo

- Settings → SWR-Limit Dropdown 1.5/2.0/2.5/...

### B5 — P60 User-Stop-Pfade

- OMNI während TX-Slot per Toggle stoppen → sofort ab.

---

## Block C — Push-Entscheidung

Wenn **Block A (F1-F10)** alle ✓:

**Sag „push" und ich:**
1. Atomare Commits für P63 (~11 Commits) erstellen
2. `git status` clean verifizieren
3. Pushen nach `origin/main`
4. Tag-Vorschlag falls gewünscht

Wenn was knackt:
- Sag mir **welcher Punkt** (z.B. „F2 — TUNE-Button bleibt ausgegraut")
- Ich debugge sofort

---

## Stand-Zusammenfassung

| Heute fertig | Status |
|---|---|
| **P58/P60/P61/Bundle K** | ✓ getestet 15.05.2026 mittags |
| **P62** Bandwechsel-UX-Pause | Field-Test pending (Block B1) |
| **P63** SWR-Block per Band-Marker | **← jetzt testen!** |

**Tests:** 1300 (Mittag) → 1306 (P62) → **1327** (P63) = +21 neue Tests heute.

**DeepSeek-V4-pro 12-Cycle-Bilanz:** 0 Halluzinationen, 100%
verifizierbar (P51 + P53 + P55 + Bundle F+G+H+I+J + P51+P58+P60+P61+P62+P63).

**Final-R1 V4-pro:** „Push freigegeben." 0 KP.
