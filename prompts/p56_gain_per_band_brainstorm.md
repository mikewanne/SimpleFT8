Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator (Mike, DK5ON).
Hardware: FlexRadio 6400 mit 2 Antennen-Slots (ANT1 = TX immer, ANT2 =
RX-only Pol-Diversity).

# P56 — Gain-Messung kollabieren auf pro-Band — Konzept-Diskussion

**KEIN Code schreiben. KEIN V1-Prompt-Review.** Nur die Logik-Optionen
vergleichen und eine Empfehlung geben.

## Was ist heute

Diversity-Gain-Messung läuft pro `(band, mode)`-Key gespeichert:
- `40m_FT8`, `40m_FT4`, `40m_FT2` jeweils separat
- 6h-Frist: nach 6 h verfällt der Eintrag, neue Messung wird beim
  nächsten Diversity-Wechsel ausgelöst
- Mess-Lauf braucht ≥ 5 Stationen sichtbar (`MIN_MEASURE_STATIONS=5`)
- 8 Schritte (`ROUNDS=2 × 2 Antennen × 2 Gain-Stufen`)
- FT8 hat per Zyklus deutlich mehr decodierbare Stationen als FT4 (kürzer)
  und FT2 (noch kürzer) → FT4/FT2-Messungen scheitern oft am
  Stations-Mangel oder hängen

**Physikalisch ist Gain eine Hardware-Eigenschaft pro Antenne pro Band**
— die Pol-/Pattern-Charakteristik einer 40m-Doppelzepp ist auf FT8/FT4/
FT2 identisch (alle nutzen denselben Empfangskreis, dieselbe
Antennen-Charakteristik). Der RF-Gain am FlexRadio-Vorverstärker ist
breitbandig pro Band, nicht protokoll-abhängig.

**Damit:** Mode-Trennung im PresetStore ist Overengineering. Pro-Band-
Key (`40m`, `20m` usw.) reicht.

## Was Mike will

Architektur-Vereinfachung:
1. PresetStore-Key wird `40m` (ohne `_FT8`-Suffix).
2. Bei Diversity-Wechsel: prüfe `40m`-Wert + Alter. Wenn frisch → nehmen.
   Wenn alt/leer → Mess-Trigger nötig.
3. Migration der alten Datei: FT8-Eintrag pro Band wird der neue Wert,
   FT4/FT2-Einträge verworfen.
4. **Kein Wahl-Dialog** für den User — silent fallback bevorzugt.

## Offene Logik-Entscheidung (DAS ist deine Frage)

Wenn auf **FT4 oder FT2** ein Mess-Trigger fällig wäre (z.B. Wert fehlt
ganz oder ist > 6 h alt), wie reagieren wir?

### Option A — „Nur FT8 misst, FT4/FT2 nutzt immer existierenden Wert"

- Mess-Dialog kommt **nur** wenn aktiver Modus FT8 ist.
- In FT4/FT2: existierenden Wert nehmen, auch wenn 9 h, 24 h, 7 Tage alt.
- Wenn gar kein Wert da ist (Erstnutzung auf FT4): passiver Hinweis
  „Bitte einmal in FT8 messen — Werte gelten dann für alle Modi".
- Implementierung: `_check_diversity_preset` prüft zusätzlich
  `self.settings.mode == "FT8"` als Vorbedingung für Mess-Trigger.

### Option B — „Auto-Modus-Switch auf FT8 zum Messen, dann zurück"

- Wenn auf FT4/FT2 Mess-Trigger fällig → App wechselt automatisch nach
  FT8, misst dort, wechselt zurück nach FT4/FT2.
- Mike sieht: kurzer FT-Mode-Wechsel-Flicker, dann Mess-Dialog, dann
  zurück.
- Werte für `40m` werden geschrieben, dann FT4 wieder aktiviert.
- Implementierung: `_check_diversity_preset` ruft vor Mess-Start
  `set_mode("FT8")`, nach Mess-Ende `set_mode(original)` + State-Restore.

### Option C — irgendeine bessere Variante die du siehst?

## Faktoren die zu bewerten sind

1. **UX:** Was sieht/spürt Mike? Wann wundert er sich?
2. **Aufwand:** Code-Pfade, Edge-Cases, Test-Aufwand
3. **Edge-Cases:**
   - Mike startet App auf FT4 ohne FT8-Wert je gemessen zu haben
   - Mike wechselt häufig zwischen FT8/FT4 (Auto-Switch könnte stören)
   - Bandwechsel + Modus-Wechsel in schneller Folge
   - Aktive QSO/CQ während Mess-Trigger fällig wird
4. **Risiken der „immer alten Wert nehmen, auch 9h+"-Strategie:**
   - Antennen-Eigenschaften saisonal? (Eis, Schnee, Boden-Feuchte)
   - Bei Hobby-Tool: relevant oder Theorie?
5. **Risiken des Auto-Mode-Switches:**
   - User-Verwirrung wenn FT4 plötzlich FT8 ist
   - State-Restore-Komplexität (TX-Slot-Lock, Frequenz, CQ-Mode)
   - Encoder-Race?

## Was ich von dir will

1. **Empfehlung:** Option A, B oder C? Mit Begründung.
2. **Aufwand-Schätzung** pro Option (kleine/mittlere/große Änderung,
   wie viele Files, Test-Coverage-Bedarf).
3. **Hidden Risks:** Was sehe ich vielleicht nicht?
4. **Hobby-Funker-Brille** (CLAUDE.md-Philosophie): KISS schlägt
   Vollständigkeit. Ist Option A „gut genug" oder gibt's einen Grund für
   die Komplexität von B?

Format: kurze Tabelle Option/UX/Aufwand/Risiko + 1-Absatz-Empfehlung.
Halluzinationen vermeiden, bei Code-Bezug Dateipfad nennen.
