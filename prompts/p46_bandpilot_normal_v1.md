# P46 — Bandpilot Normal-Reintegration (V1, 13.05.2026)

**Status:** V1 — geht in V2 → R1 → V3 → Code.

**Trivial-Klausel:** nein — Verhaltens-Aenderung an Bandpilot-Strategie,
bestehende Tests muessen angepasst werden, neue Tests fuer Normal-Pfad.

---

## 1. Was Mike will (Vision-Aenderung 12.05.2026)

**Aktueller Stand (P35-Bug-E vom 11.05.2026):** Bandpilot empfiehlt NIE
Normal. `mw_radio.py:778-779` skipt `current == "normal"` komplett,
`:815-816` blockt `target == "normal"` defensiv.

**Mike's neue Vision (TODO P46, 12.05.2026, mit R1-Konsens):**
„ganz oder gar nicht — wenn schon Pilot, dann alle 3 Modi. 95% der
Baender verliert Normal — aber die 5% Spezialfaelle (duenne Datenbasis
17m/12m, resonante 20m-Antenne in ruhigen Stunden, Single-Antenna-
Setups) rechtfertigen den Aufwand."

P35-Bug-E war damals defensiv weil Bandpilot nur Diversity-Vergleich
war. Jetzt 3-Wege-Logik im Recommender → Normal legitim als Kandidat.

## 2. Code-Verifikation (Schritt 0 Ergebnisse)

**Schon 3-Wege-faehig (NICHT anfassen):**
- `core/mode_recommender.py` — `CODE_MODES = ("normal", "diversity_normal", "diversity_dx")`. `recommend_for_hour` sammelt Means fuer alle 3 Modi, Ranking ist 3-elementig.
- `core/mode_recommender.py` Schwellen `MIN_DAYS_HOUR=3` + `MIN_CYCLES_HOUR=20` gelten schon fuer alle 3 Modi (alle muessen erfuellen).
- `ui/bandpilot_dialogs.py::BandpilotManualDialog` — zeigt schon 3 Buttons, einer pro Modus, mit Markern und Top-1-gruen.
- `ui/bandpilot_dialogs.py::BandpilotAutoToast` — zeigt schon Ranking aller 3 Modi.
- `ui/settings_dialog.py` ToolTip — erwaehnt schon „Normal / Diversity Standard / Diversity DX".

**Was BLOCKIERT (P46-Ziel: entfernen):**
- `ui/mw_radio.py:774-779` — `if current == "normal": return False` skip.
- `ui/mw_radio.py:811-816` — `if target == "normal": return False` block.

**Tests die Workaround nutzen (anpassen):**
- `tests/test_mw_radio_bandpilot.py` — mehrere Tests setzen
  `current="diversity_normal"` mit Kommentar „P35 Bug E: ... damit Bandpilot wirkt". Diese Kommentare + Workaround-Settings sind hinfaellig.

## 3. Loesungsumfang

### Maßnahme 1 — `_maybe_apply_bandpilot` Normal-Skip entfernen

`ui/mw_radio.py:774-779`:
```python
# P35 Bug E (Mike-Diagnose 11.05.): Bandpilot ueberschreibt
# Mike's manuelle Normal-Entscheidung NIE. Bandpilot's Aufgabe ist
# NUR zwischen Diversity-Standard und Diversity-DX zu waehlen —
# ob Mike ueberhaupt Diversity will, entscheidet Mike selbst.
if current == "normal":
    return False
```

→ **Block ersatzlos streichen.** Bandpilot greift jetzt auch in Normal.

### Maßnahme 2 — `_apply_bandpilot_auto` Normal-Target-Block entfernen

`ui/mw_radio.py:811-816`:
```python
# P35 Bug E: Bandpilot empfiehlt NIE Normal. Defensive — sollte
# durch Recommender-Logik schon abgedeckt sein, aber falls dort
# Normal als Top-1 erscheint (z.B. wenige Diversity-Daten):
# Mike-Regel "Normal ist Mike's Entscheidung" enforced.
if target == "normal":
    return False
```

→ **Block ersatzlos streichen.** Normal ist legitimer Target.

### Maßnahme 3 — Bestehende Tests entwerten / aktualisieren

`tests/test_mw_radio_bandpilot.py` — 4 Tests verwenden
`current="diversity_normal"` mit Kommentar „P35 Bug E damit Bandpilot
wirkt". Diese Kommentare + Workaround-Argumentation **wird hinfaellig**.

Die Tests selbst funktionieren weiter (sie testen den Switch-Pfad), aber
die Begruendung in Kommentaren ist veraltet. Optionen:
- **(A) Kommentare aktualisieren** (Workaround-Hinweis raus), Tests
  bleiben sonst gleich.
- **(B) Tests umstellen auf `current="normal"`** — testet die neue
  Logik direkt.

→ **V3-Empfehlung Option B.** Begruendung: Tests testen jetzt die
realistische Praxis „User ist im Normal-Modus, Bandpilot bietet
Diversity-Wechsel an". Mehr Aussagekraft.

### Maßnahme 4 — Neue Tests fuer Normal-Pfade

`tests/test_p46_bandpilot_normal.py` NEU — 5 neue Tests:
- **T1** Auto: current=normal, top1=diversity_dx, decision=switch → wechselt zu diversity_dx
- **T2** Auto: current=diversity_dx, top1=normal, decision=switch → wechselt zu **normal** (vorher von P35-Bug-E geblockt)
- **T3** Auto: current=normal, top1=normal, decision=no_change → nichts
- **T4** Manual: current=normal, top1=diversity_normal → Dialog wird gezeigt
- **T5** Manual: current=diversity_dx, top1=normal → Dialog wird gezeigt, Normal-Button waehlbar

### Maßnahme 5 — Doku-Updates

- `docs/explained/bandpilot_de.md` (falls existiert) — Hinweis dass Normal jetzt empfohlen werden kann
- `docs/explained/bandpilot.md` (EN) — analog
- `ui/settings_dialog.py` ToolTip — schon korrekt
- `BandpilotAutoToast` / `BandpilotManualDialog` — schon korrekt (3 Modi)

## 4. Akzeptanzkriterien

| AK | Bedingung | Verifikation |
|---|---|---|
| **AK1** | `mw_radio.py` enthaelt KEIN `if current == "normal": return False` mehr | grep |
| **AK2** | `mw_radio.py` enthaelt KEIN `if target == "normal": return False` mehr | grep |
| **AK3** | `_maybe_apply_bandpilot` mit `current="normal"` + decision=switch ruft `_apply_bandpilot_auto` auf | T1 |
| **AK4** | `_apply_bandpilot_auto` mit `target="normal"` ruft `_set_rx_mode_direct("normal")` auf | T2 |
| **AK5** | Bestehende Bandpilot-Tests bleiben grün (mit Updated-Kommentaren) | pytest |
| **AK6** | Bandpilot-Strategie konsistent: 3-Wege-Vergleich in allen UI-Pfaden | Visual / Manual-Dialog |
| **AK7** | **Mike's „App-Start IMMER 20m FT8 Normal" (P35-Bug-F) bleibt unveraendert** — Bandpilot greift erst bei Band-Wechsel, nicht beim App-Start | Code-Review |

## 5. Files

| Datei | Aenderung |
|---|---|
| `ui/mw_radio.py` | 2 Code-Bloecke entfernen (`:774-779` + `:811-816`) |
| `tests/test_mw_radio_bandpilot.py` | 4 Tests: Workaround-Kommentare raus, `current="normal"` setzen wo sinnvoll |
| `tests/test_p46_bandpilot_normal.py` NEU | 5 neue Tests (T1-T5) |
| `main.py` | APP_VERSION 0.97.16 → 0.97.17 |
| `docs/explained/bandpilot_de.md` + `.md` | Doku-Hinweis falls Datei existiert |

**KEIN Touch:**
- `core/mode_recommender.py` (schon 3-Wege-faehig)
- `ui/bandpilot_dialogs.py` (zeigt schon 3 Modi)
- `ui/settings_dialog.py` (ToolTip schon korrekt)
- `config/settings.py` (Migration unveraendert)

## 6. Risiken

| R | Risiko | Mitigation |
|---|---|---|
| R1 | Bandpilot wechselt User unerwartet von Diversity auf Normal | Mike-Wunsch — bewusst, R1-Konsens. Auto-Toast 5 Sek + Manual-Dialog warnen visuell. |
| R2 | Mike vergisst dass P35-Bug-E zurueckgenommen ist und wundert sich ueber Wechsel-Vorschlag | HISTORY.md + Memory dokumentiert die Vision-Aenderung |
| R3 | P35-Bug-F (App-Start IMMER Normal) wird versehentlich auch zurueckgesetzt | AK7 — Code-Review: P35-Bug-F ist in `main_window.__init__`, nicht in mw_radio Bandpilot-Pfad. ORTHOGONAL. |
| R4 | Tests die Workaround nutzten brechen ohne Anpassung | Maßnahme 3 — Tests aktualisieren in einem Commit |
| R5 | Manual-Dialog-Button fuer Normal wurde bisher nie geklickt → Latent-Bug-Moeglichkeit | Dialog-Code in `bandpilot_dialogs.py:177-184` iteriert ueber alle 3 Modi → Button-Click-Pfad ist identisch fuer alle 3 → keine Sonderlogik. Test T5 deckt ab. |

## 7. Backup & Commits

**Backup:** `Appsicherungen/2026-05-13_v0.97.16_vor_p46_bandpilot_normal/`
mit `ui/mw_radio.py` + `tests/test_mw_radio_bandpilot.py`.

**Atomare Commits:**
- **C1** `ui/mw_radio.py` — beide Skip-Bloecke entfernen + Kommentare an aktuelle Strategie anpassen
- **C2** `tests/test_mw_radio_bandpilot.py` — Workaround-Kommentare raus, `current="normal"` wo sinnvoll
- **C3** `tests/test_p46_bandpilot_normal.py` — 5 neue Tests
- **C4** `main.py` — APP_VERSION 0.97.17
- **C5** Doku: HISTORY + HANDOFF + CLAUDE + Memory + TODO + ggf. `docs/explained/bandpilot_de.md`

## 8. Mike-Klaerung (wird in V3 ueberholt)

Q1: P35-Bug-E hatte einen Grund — bleibt P35-Bug-F (App-Start Normal) unveraendert?
A1: **JA** — orthogonal. P35-Bug-F ist in `main_window.__init__` Initial-Setup, kein Bandpilot-Pfad.

Q2: Soll der Bandpilot bei rein-Normal-Stationen (kein Diversity-Setup) trotzdem laufen?
A2: **Ja** — wenn Daten fuer alle 3 Modi vorhanden sind (Schwelle MIN_DAYS_HOUR/MIN_CYCLES_HOUR). Bei Single-Antenna-Setups sind die Diversity-Daten leer → Recommender liefert `None` → Bandpilot still. Bereits korrekt.

Q3: Soll Bandpilot in Auto-Modus den Modus-Wechsel zu Normal **WARNEN** statt sofort wechseln?
A3: **Nein** — Konsistent mit Diversity-Wechseln. Toast zeigt Modus + Werte, User kann reagieren.

---

**Naechster Schritt:** V2 (Self-Review) — was uebersieht V1?
