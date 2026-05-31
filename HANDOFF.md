# HANDOFF — SimpleFT8

**Aktueller Stand:** v0.98.49 (31.05.2026) — **Diplome-Feature (DXCC/WAC/WAS/WAZ)**
im Logbuch-Tab. Tests 2228 grün (+16). **Lokal NICHT committet/gepusht — siehe unten.**

---

## Letzte Session (31.05.2026)

### Diplome-Feature (NEU, v0.98.49) — voller DeepSeek-Workflow

Mike-Auftrag: DXCC-Label im Logbuch-Tab durch Button **„Diplome"** ersetzen →
Dialog mit Übersicht der 4 Diplome (gearbeitet + per LoTW bestätigt), mit
Staffelung wo offiziell vorhanden. DO4MHH (Mikes altes Klasse-E-Call) zählt mit.

**Umgesetzt:**
- `core/awards.py` (NEU): `compute_awards(records)` → pro Diplom worked+confirmed
  Sets. DXCC (Entity-Nr, Ziel 100), WAC (6 Kontinente, AN ausgeschlossen), WAS
  (50 US-States via `US_STATES`-frozenset, AK/HI drin), WAZ (40 CQ-Zonen).
  Bestätigt = NUR `LOTW_QSL_RCVD=Y`. `dxcc_tier_status()` für ARRL-Marken
  100/150/200/250/300/Honor Roll. Beide Calls = ein Pool (set-dedup).
- `ui/awards_dialog.py` (NEU): read-only Dialog, dunkles Theme, pro Diplom Karte
  + Fortschrittsbalken + „🏅 erreicht"-Badge; DXCC mit Marken-Zeile.
  Datenquellen-Hinweis (QRZ-Export DA1MHH & DO4MHH).
- `ui/logbook_widget.py` (Edit): `dxcc_label` → `btn_awards` „Diplome";
  `_on_awards_clicked` lädt `adif/_backup_qrz_export` **on-demand** dazu;
  `_update_counters` ohne dxcc_label; Import AwardsDialog.
- `tests/test_awards.py` (NEU): 16 Tests (distinct-Zählung, LoTW-Filter,
  US-State-Validierung, AN-Ausschluss, CQ-Zonen-Range, DXCC-Staffelung, robust).

**Datenquelle:** Diplome werten den QRZ-Export (`adif/_backup_qrz_export/`,
18.329 QSOs DA1MHH+DO4MHH) on-demand beim Dialog-Öffnen aus — die reichen Felder
(DXCC/CONT/STATE/CQZ/LOTW) stecken nur dort. Frische SimpleFT8-QSOs zählen erst
nach erneutem QRZ-Export mit (dokumentiert im Dialog-Hinweis).

**Staffelung (DeepSeek R1b Option A):** Nur DXCC hat eine echte numerische
ARRL-Leiter → die wird gezeigt. WAC/WAS/WAZ sind „alles-oder-nichts" → Fortschritt
+ Badge, KEINE erfundenen Bronze/Silber/Gold (Ehrlichkeit > Gamification).

**DeepSeek-Workflow:** V1→V2→Design-R1 (GO, 6 Auflagen — alle umgesetzt:
try/except DXCC, WAC ohne AN, LoTW-only, US-State-Filter, Button+on-demand,
Datenquellen-Hinweis) + R1b (Staffelung Option A). **Final-R1 (Bestätigungs-Pass)
konnte wegen Session-Tooling-Instabilität nicht eingelesen werden** — die
DeepSeek-Läufe lieferten nach ~8 Aufrufen keinen lesbaren Output mehr. Design-R1
hatte die exakten Code-Pfade aber bereits geprüft; alle Auflagen sind im Code
verifiziert + 16 Unit-Tests + 0 Regressionen. **Explizites Final-R1 vor Push
nachholen.**

**Tests:** Volle Suite **2228 passed, 0 Regression** (18.33s). 16 neue Award-Tests.

---

## ⛔ OFFEN

1. **Final-R1 nachholen** (Tooling-bedingt nicht abgeschlossen), DANN
2. **Lokaler Commit** des Diplome-Features (noch nicht committet wegen Tooling).
3. **Push-Freigabe** durch Mike (Standing-Regel) — zusammen mit den 3 älteren
   nicht-gepushten Commits (cd91712 P162-Revert, 9034884 P164, 725cedc HANDOFF).
4. **Field-Test** Diplome-Button am Radio (Optik + reale Zahlen prüfen).

## TODO (Mike-Wunsch, zurückgestellt)
- **„neue"-Filter + Auto-Hunt mit voller QRZ-Historie füttern:** den
  `_backup_qrz_export`-Ordner zusätzlich in `QSOLog` (`log/qso_log.py`,
  Worked-Before-Set) laden, damit NEUE-Filter + Auto-Hunt die echte 18k-Historie
  kennen (aktuell nur die paar hundert SimpleFT8-eigenen QSOs). Eigener
  Workflow. → in TODO.md.

---

## ⚠ Tooling-Warnung (diese Session durchgehend)
Bash-stdout-Display + /tmp-Scratch-Reads zeitweise leer; DeepSeek-Läufe ab
~8 Aufrufen ohne lesbaren Output; lange Befehle auto-backgrounden. **Write/Edit
+ pytest persistierten zuverlässig** (Code real geschrieben, Suite real grün).
Verifikation NUR über pytest-Returncode + grep-in-Datei, nicht der Anzeige
trauen. Lesson: Bash(write)+Read(file) NICHT im selben Message-Block (Race) —
getrennte Messages.
