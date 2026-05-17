# Field-Test-Abarbeitungsliste — 17.05.2026

**Sortiert: einfach/schnell zuerst → schwer/umfangreich zuletzt.**
Ziel: Verifizieren dass die Arbeit aus v0.97.40-46 in der Praxis hält
bevor wir alles zusammen pushen.

**App-Start:**
```
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
./venv/bin/python3 main.py
```

---

## 🟢 STUFE 1: Einfach + schnell, kein Radio nötig (~15 Min)

### F-S1.1 Bundle-L-Revert (v0.97.40, 1 Min)
**App starten ohne Radio.** ConnectStatusDialog erscheint mit zwei Buttons.
- Klick **„ohne Radio weiter"** → Dialog schließt, App läuft im Demo-Modus
  weiter (kein Quit, anders als zwischen v0.97.38-39).
- Klick **„Beenden"** → App-Quit.

✅ Beide Buttons machen jetzt verschiedene Sachen (vor Revert: beide gleich).

### F-S1.2 P52 Stats-Toggle (v0.97.41, 2 Min)
**Settings öffnen.** Tab „FT8 & Diversity".
- Settings-Toggle „Statistik-Erfassung aktivieren" ist **nicht mehr vorhanden**
  (komplett raus).
- App-Start-Log zeigt einmalig: `[Stats-Cleanup] N Dateien älter als 90 Tage gelöscht: 0` (oder N>0 falls alte Stats existieren).

✅ Toggle weg, Cleanup-Log einmal sichtbar.

### F-S1.3 P66 Logbuch-Tab-Auto-Show (v0.97.42, 2 Min)
**Logbuch-Tab öffnen.** Mindestens 1 QSO-Zeile selektieren.
- Tab-Wechsel zu QSO-Tab → Tab-Wechsel zurück zu Logbuch.
- **Detail-Overlay rechts erscheint automatisch** (Mike-Vorschlag 16.05.).

✅ Kein manueller Re-Click nötig.

### F-S1.4 P67 ohne Radio (v0.97.43, 5 Min) — F1+F3+F5
**Auto-Hunt-Button starten** (oder via Tooltip aufrufen wenn nicht
sichtbar — Diversity-Modus aktiv setzen).
- **F1:** Direkt nach Toggle ON → Statusbar zeigt Auto-Hunt aktiv, kein
  Sofort-Stop (Anker wurde korrekt gesetzt VOR start_auto_hunt).
- **F3:** Mausbewegung → Anker resettet, kein Stop nach 5 Min wenn
  alle paar Minuten bewegt.
- **F5:** UI-Hinweistext im Stop-Modal zeigt „AUTO HUNT-Taste drücken
  zum Fortsetzen" (R1-S7 Verbesserung).

✅ Auto-Hunt-Logik reagiert auf Maus.

### F-S1.5 P69 Bootstrap-CI in PDF (v0.97.46, 5 Min)
**PDF öffnen:** `auswertung/Auswertung-40m-FT8.pdf` Seite 3.
- Vergleichstabelle hat in der **„vs Normal"-Spalte 2 Zeilen** pro Modus:
  Punktschätzer + 95%-CI (z.B. `+62%` / `+32–+102%`).
- Methodik-Caveat unten erwähnt Block-Bootstrap.

**PDF öffnen:** `auswertung/Auswertung-20m-FT8.pdf` Seite 3.
- 20m-Tabelle zeigt CI mit Null-Überdeckung (negative-positive Range).

**README in GitHub-Markdown-Preview öffnen:**
- 6 Tabellen DE+EN zeigen neue Werte mit 95%-CI-Spalte.

✅ PDF + README sehen sauber aus, keine Layout-Bugs.

---

## 🟡 STUFE 2: Mittel, mit Radio nötig (~30 Min)

### F-S2.1 P67 mit Radio (v0.97.43, 10 Min) — F2+F4
**Radio verbunden, Diversity-Modus aktiv, Auto-Hunt an.**
- **F2:** 5 Min Maus NICHT bewegen → Auto-Hunt stoppt automatisch
  mit Console-Log `mouse_inactive_5min`. Modal zeigt „AUTO HUNT-Taste
  drücken zum Fortsetzen".
- **F4:** Während Auto-Hunt-Pause läuft ein QSO → wartet QSO-Ende ab
  (kein `_abort_active_tx`), dann stoppt Auto-Hunt.

✅ 5-Min-Maus-Logik greift sauber, QSO-Schutz funktioniert.

### F-S2.2 P54 Auto-Tune Bandwechsel ohne Stützpunkt (v0.97.44, 10 Min)
**Radio verbunden, Settings → „Auto-TUNE bei Bandwechsel" AN.**
- **F1:** Bandwechsel 20m → 40m → **AutoTuneDialog öffnet** mit Spinner.
  15s TUNE → Dialog schließt automatisch bei SWR-Good. Console:
  `[P54b] RFPreset-Stuetzpunkt: 40m_10W → rf=10`
- **F4:** Settings „Auto-TUNE bei Bandwechsel" → AUS. Bandwechsel →
  KEIN Dialog mehr.
- **F7:** Cancel-Button im Dialog während TUNE → Dialog schließt
  sauber, kein Save, Marker bleibt unangetastet.

✅ Dialog erscheint, schließt, Cancel funktioniert.

### F-S2.3 P54 Auto-Tune Edge-Cases (v0.97.44, 10 Min)
- **F2:** Auto-Tune auf SWR-blockiertes Band (Marker aktiv) → KEIN
  Dialog (Skip respektiert).
- **F3:** Bandwechsel mit Antennen-Mismatch (z.B. ohne Tuner-Match) →
  Timeout/Fail → Status „TUNE fehlgeschlagen", Marker setzt.
- **F5:** Mode-Wechsel FT8↔FT4 OHNE Bandwechsel → kein Auto-Tune.

✅ Skip-Logik greift, Mode-Wechsel triggert kein Auto-Tune.

---

## 🔴 STUFE 3: Schwer + umfangreich, alles am Radio (~60 Min)

### F-S3.1 P54-FIX Closed-Loop auf resonantem Band (v0.97.45, 10 Min) — F1
**Auf 40m (resonant für ANT1).** TUNE-Button drücken.
- **Phase A** (10s): Console zeigt rfpower=10 fest, Tuner-Match.
- **Phase B** (5s max): Console zeigt Convergenz-Iterationen,
  z.B. `[P54-FIX] Iter 1: fwdpwr=8.2, rf=10 → 12. Iter 2: fwdpwr=9.8,
  rf=12 → 12 (stable).`
- Finaler rf-Wert plausibel (10-15). Save in Settings-Tabelle sichtbar
  als `40m_10W: rf=12`.

✅ Convergenz funktioniert auf resonantem Band.

### F-S3.2 P54-FIX auf Off-Band 17m mit SWR 2,5:1 (v0.97.45, 10 Min) — F2
**Auf 17m wechseln** (off-band für ANT1, SWR höher).
- TUNE → Convergenz auf HÖHEREN rf-Wert (z.B. 16-22) weil weniger
  Effizienz.
- Console zeigt mehr Iterationen.
- Settings-Tabelle zeigt `17m_10W: rf=18` o.ä.

✅ Closed-Loop kompensiert Antennen-Effizienz richtig.

### F-S3.3 P54-FIX SWR-Bad-Skip (v0.97.45, 5 Min) — F3
**Auf einem nicht-matchbaren Band** (z.B. 60m falls Tuner versagt) TUNE.
- Phase B SKIP (SWR > Limit auch nach Phase A).
- **Kein Save** in Settings-Tabelle.
- Band-Marker bleibt rot.

✅ SWR-Schutz funktioniert.

### F-S3.4 P54-FIX Krücke + Tabelle-Aufbau (v0.97.45, 15 Min) — F4+F5
**Erstes QSO 50W auf neuem Band** ohne 50W-Eintrag in Tabelle.
- **F4:** Console zeigt `[RF-Preset] Krücke: 40m_50W → rf=...`
  (Krücken-Skalierung × 0.9 aus 10W-Anker).
- **F5:** Nach mehreren Sessions zeigt Settings-Tabelle echte
  band-spezifische Werte: 10W-Anker + höhere Wattzahlen aus
  QSO-Convergenz. Pro Band individuell.

✅ Krücke greift, Tabelle wächst organisch mit echten Werten.

### F-S3.5 P54-FIX Cancel + Hardware-Fehler (v0.97.45, 10 Min) — F6+F7
- **F6:** Während TUNE → Cancel-Button drücken → Schleife bricht ab,
  kein Save, Hardware sauber (kein hängender TX-State).
- **F7:** Mit Hardware-Fehler simulieren (z.B. Antenne abziehen während
  Convergenz, FWDPWR=0) → Fallback rf=10, kein Crash, Console-Log
  zeigt Fehlerbehandlung.

✅ Cancel-Race + DIV0-Robustheit funktioniert.

### F-S3.6 P54-FIX Manueller TUNE (v0.97.45, 5 Min) — F8
**Klassischer TUNE-Button-Klick** (kein Auto-Tune via Bandwechsel).
- Identische Phase A + B + Save-Logik wie Auto-Tune.

✅ Konsistente Logik in beiden Pfaden.

---

## 📦 STUFE 4: Nach allen Field-Tests → Push (Mike-Freigabe)

Wenn STUFE 1-3 alle ✅ → gemeinsamer Push aller pending Commits
v0.97.40-46 zu GitHub. Damit ist auch der CQ-DL-6/2026-Klarstellungs-
block + die neuen Block-Bootstrap-CIs in der README für Leser sichtbar.

**Tag-Empfehlung:** `v0.97.46` mit Release-Notes aus HISTORY.md
(Sektionen 0.97.40 bis 0.97.46).

```bash
git push origin main
git tag -a v0.97.46 -m "v0.97.46: P54-FIX + P67 + P54 + P52 + P66 + P69 + Bundle-L-Revert"
git push origin v0.97.46
```

---

## Bilanz Aufwand vs. Sicherheit

- **STUFE 1 (~15 Min):** 5 Punkte, schnell weg, kein Radio nötig.
  Wenn STUFE 1 grün, sind 5 von 6 Versionen verifiziert.
- **STUFE 2 (~30 Min):** 3 Punkte mit Radio, mittlere Komplexität.
- **STUFE 3 (~60 Min):** 6 Punkte am Radio, hauptsächlich P54-FIX
  (das war die komplexeste Arbeit der Session).

**Gesamt-Field-Test-Aufwand: ~1h45m am Radio + 15 Min am Schreibtisch.**

Wenn du nur Zeit für STUFE 1+2 hast: schon 8 von 14 Field-Test-Punkten
abgehakt. STUFE 3 kann auch in einer späteren Funk-Session sein.
