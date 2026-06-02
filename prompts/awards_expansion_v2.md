# Plan-Review: Diplome-Erweiterung (WAE + WPX + DXCC-Band-Tiefe + Sichtbarkeit)

Du bist Zweit-Reviewer (DeepSeek v4-pro) für ein **Hobby-Funker-FT8-Tool**
(SimpleFT8, PySide6/Python, EIN Operator: Mike, DL, ~18.000 historische QSOs
via QRZ-Export). KEIN Contest-Tool. Leitsätze: **KISS, Overengineering
vermeiden, drei ähnliche Zeilen schlagen eine verfrühte Abstraktion,
Code als Referenz statt Annahmen.** Antworte kritisch und konkret.

## Kontext / Ist-Zustand (verifiziert im Code)

Es existiert bereits ein schlankes Diplome-Feature:
- `core/awards.py` — reines Berechnungsmodul (KEINE UI/IO). `compute_awards(records)`
  liefert pro Diplom `{label, goal, worked:set, confirmed:set}` für **DXCC, WAC,
  WAS, WAZ**. DXCC zusätzlich mit Marken-Tiers (100/150/200/250/300) + Honor Roll.
  Bestätigt = ausschließlich `LOTW_QSL_RCVD == "Y"`.
- `ui/awards_dialog.py` — modaler Dialog, eine Karte (`QFrame`) pro Diplom in
  `AWARD_ORDER`, Fortschrittsbalken + Badge "🏅 erreicht" / "x/goal".
- `ui/logbook_widget.py` — Button "Diplome" → `_on_awards_clicked()` lädt records
  + QRZ-Backup on-demand → `AwardsDialog(records, self).exec()`.
- Datenquelle: `adif/_backup_qrz_export/` (DA1MHH + DO4MHH), beide Calls in EINEN
  Pool (set-basiert dedupliziert).

### Verifizierte Datengrundlage (grep über 12.024 QSOs DA1MHH)
| ADIF-Feld | Abdeckung | Nutzbar für |
|---|---|---|
| `DXCC` (Entity-Nr) | 12016/12024 (99,9%) | DXCC ✅, WAE-Filter |
| `CONT` (Kontinent) | 12016/12024 | WAE (CONT==EU) ✅ |
| `STATE` | bei US gefüllt, sonst N/A | WAS ✅ |
| `CQZ` | 12013/12024 | WAZ ✅ |
| `CALL` | 12024/12024 (100%) | WPX (Präfix-Parsing) ✅ |
| `BAND` | 12024/12024 (gemischt "20m"/"20M") | DXCC-Band-Tiefe ✅ |
| `PFX` | **nur 5514/12024 (46%)** | WPX-Stütze (unzuverlässig) |
| `IOTA` | **überall "N/A"** | IOTA ❌ nicht machbar |
| `LOTW_QSL_RCVD` | 11992/12024 | Bestätigung ✅ |
| DOK | **gar nicht vorhanden** | DLD ❌ nicht machbar |

DA1MHH allein: 145 eindeutige DXCC-Entities. Bänder (Anzahl QSOs):
20m 3750 / 40m 2432 / 30m 2203 / 80m 1018 / 15m 965 / 60m 584 / 17m 571 /
12m 240 / 10m 230 / 2m 16 / 6m 15.

### Settings-Architektur (verifiziert)
- KEIN Singleton: `Settings()` wird in `main.py:404` erzeugt, an `MainWindow`
  übergeben (`self.settings`). `qso_panel.__init__()` und `LogbookWidget()`
  bekommen settings **NICHT** (Konstruktoren ohne Args).
  Kette: MainWindow(settings) → qso_panel (LogbookWidget()) → AwardsDialog.
- Persistenz-Muster vorhanden: `settings.get_enabled_bands()/set_enabled_bands()`
  (P50, Band-Sichtbarkeit in config.json) — exakte Vorlage für Award-Sichtbarkeit.
- Andere Module haben EIGENE JSONs in `~/.simpleft8/` (dt_corrections.json,
  preset_store, etc.) — alternatives Persistenz-Muster.

## Mike-Entscheidungen (fix, nicht zur Debatte)
1. Neue Diplome: **WAE + WPX + DXCC-Band-Tiefe** (DLD raus = DOK fehlt, akzeptiert).
2. Sichtbarkeit: **Auge-Symbol pro Karte** + aufklappbarer "Ausgeblendet (N)"-
   Bereich unten, Klick blendet wieder ein. Persistent über App-Neustarts.

---

# V1 — Entwurf

## A) WAE (Worked All Europe, DARC)
- `compute_awards`: WAE-worked = Menge eindeutiger `DXCC`-Entities mit `CONT=="EU"`.
  Confirmed = davon LoTW-Y.
- Ziel-Konstante `WAE_GOAL`. Offizielle WAE-Liste hat ~70 Gebiete.
- **Datengrundlage-Frage 1:** feste WAE-DXCC-Nummern-Liste hinterlegen (exakt,
  aber Pflege-Aufwand + die WAE-Liste hat Sonder-Multiplier wie IT9-Sizilien,
  GM-Shetland, eu-Russland-Distrikte die NICHT 1:1 DXCC-Entities sind) **ODER**
  einfache Näherung "eindeutige europäische DXCC-Entities (CONT==EU)" mit
  ehrlichem Tooltip "Näherung über europäische DXCC-Länder"?

## B) WPX (Worked All Prefixes, CQ)
- Neue Modul-Funktion `wpx_prefix(call) -> str | None`.
- Regel (FT8-tauglich): führender `[A-Z0-9]`-Teil bis einschließlich **letzter
  Ziffer**, gefolgt von reinem Buchstaben-Suffix. Regex `^([A-Z0-9]*\d)[A-Z]+$`.
  Beispiele: `DA1MHH→DA1`, `9A7W→9A7`, `K5ZD→K5`, `2E0ABC→2E0`, `OH8X→OH8`.
- Slash-Calls: `core/geo.py` hat bereits `_strip_mobile_suffix()` +
  `_dxcc_prefix_from_call()` (P1.LOCATOR-SLASH). Wiederverwendbar für WPX?
- worked = Menge eindeutiger Präfixe. `WPX_GOAL = 300` (CQ-Basis).
- **Frage 2:** PFX-Feld (46% da) nutzen wo vorhanden, sonst Parser — oder
  IMMER aus CALL parsen (konsistent)? Ich tendiere zu **immer parsen**.
- **Frage 3:** WPX-Tiers wie DXCC (300/350/400/450/500) — oder nur Basis 300?

## C) DXCC-Band-Tiefe
Mike wählte "DXCC-Bänder". Zwei etablierte Diplome:
- **5-Band-DXCC**: 100 Entities (bestätigt) auf JEDEM von 80/40/20/15/10m.
- **DXCC Challenge**: Summe eindeutiger (Entity,Band)-Slots über alle Bänder,
  Ziel 1000.
- **Frage 4:** Beide als Erweiterung der bestehenden DXCC-Karte (Sub-Zeilen)
  zeigen, oder nur EINES? Als eigene Top-Level-Karte oder als DXCC-Detail?
  Ich tendiere zu: DXCC-Challenge-Zähler (1 Zahl, schöner Langzeit-Balken) +
  5BDXCC-Mini-Statuszeile "5BDXCC: 80✓ 40✓ 20✓ 15✗ 10✗" UNTER der DXCC-Karte —
  KEINE neue Top-Level-Karte. Band-String upper-normalisieren ("20m"→"20M").
- **Self-Review-Bedenken:** Riecht nach Overengineering für ein Hobby-Tool.
  Reicht evtl. nur der Challenge-Zähler? Bitte KISS-Urteil.

## D) Sichtbarkeit ein-/ausblenden
- **Frage 5 (Architektur):** Persistenz-Weg —
  (a) `settings.get_enabled_awards()/set_enabled_awards()` analog `get_enabled_bands`
      + settings durch 3 Konstruktor-Ebenen durchreichen
      (MainWindow→qso_panel→LogbookWidget→AwardsDialog), ODER
  (b) eigenes Mini-Modul `core/awards_prefs.py` (load/save zu
      `~/.simpleft8/awards_visibility.json`), Dialog nutzt es direkt, KEIN
      Durchreichen, voll testbar.
  Ich tendiere zu **(b)** — entkoppelt, KISS, kein invasives Durchreichen,
  testbar ohne GUI. DeepSeek: Gegenargument?
- UI: jede Karte bekommt rechts oben ein 👁-Button → toggelt → speichert → Karte
  in Klappbereich. Klappbereich unten: "▸ Ausgeblendet (N): WAC, WAS" klickbar.
- Default: alle 6 sichtbar. Defensive Filterung gegen unbekannte Keys.

## E) Tests + Doku
- `tests/test_awards_expansion.py`: WAE-Zählung, WPX-Parser-Edge-Cases
  (Slash, kein-Suffix, Mobile), DXCC-Band, Sichtbarkeits-Persistenz.
- HISTORY/HANDOFF/CLAUDE-Header/FEATURES(neuer §)/TODO/Memory.

---

# V2 — Self-Review (eigene Bedenken vor DeepSeek)
1. **WAE-Genauigkeit vs Ehrlichkeit:** Mike-Regel "nur behaupten was verifizierbar".
   CONT==EU-Näherung ist NICHT das exakte offizielle WAE. Tooltip-Kennzeichnung
   reicht? Oder ist die feste Liste die ehrlichere Wahl?
2. **WPX-Parser-Korrektheit:** Regex `^([A-Z0-9]*\d)[A-Z]+$` scheitert bei Calls
   OHNE Ziffer (gibt's praktisch nicht) und bei Suffix-Ziffern. Robust genug?
   Slash-Calls korrekt? Brauche ich den geo.py-Helper oder eigene KISS-Logik?
3. **DXCC-Band = Overengineering?** Mike wollte es zwar, aber sauberste minimale
   Form finden. Beide Diplome oder eines?
4. **Sichtbarkeit-Persistenz:** (a) settings-konsistent aber invasiv vs
   (b) eigene Datei entkoppelt. Welche ist die saubere Architektur hier?
5. **Konstruktor-Signatur-Bruch:** AwardsDialog(records, parent) — wenn ich
   enabled-Awards reinreiche, ändere ich die Signatur. Bestehende Tests?
6. **Karten-Rebuild bei Toggle:** Beim Ein-/Ausblenden muss der Dialog die
   Kartenliste neu aufbauen (oder Karten nur show/hide). Welcher Weg sauberer?

# Fragen an dich (priorisiert)
1. WAE-Datengrundlage: feste Liste vs CONT==EU-Näherung — was ist für ein
   ehrliches Hobby-Tool richtig?
2. WPX-Parser: ist die Regex-Regel korrekt+robust? Konkrete Gegenbeispiele?
   PFX-Feld nutzen ja/nein?
3. DXCC-Band-Tiefe: KISS-Minimum — beide, eines, oder weglassen?
4. Sichtbarkeit-Persistenz (a) vs (b): deine Empfehlung mit Begründung.
5. Übersehe ich etwas Strukturelles? Ist der Gesamt-Scope KISS-konform oder
   blähe ich das Hobby-Tool auf?

Bitte je Frage eine klare Empfehlung + Begründung, und markiere Findings nach
Schwere (🔴 Blocker / 🟠 wichtig / 🟡 nice-to-have).
