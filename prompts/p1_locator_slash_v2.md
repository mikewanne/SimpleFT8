# P1.LOCATOR-SLASH V2 — Self-Review von V1

**Stand:** 2026-05-07.
**Workflow:** V1 ✅ → **V2 (diese Datei)** → R1 (DeepSeek) → V3 → Compact → Code.
**Aufgabe Self-Review:** mit frischen Augen lesen — was fehlt, was ist
mehrdeutig, was hat V1 uebersehen?

---

## Lessons (L1-L12)

### L1 — Decoder-Output muss verifiziert werden bevor wir Set-Pfad anfassen

V1 nimmt an: `m.caller` ist `EA8/DA1MHH` wie auf der Frequenz gesendet.
**Aber stimmt das?** ft8lib parst FT8-Messages und liefert die 3
Felder (`field1`, `field2`, `field3`) sowie `caller` (= field2 in der
Regel). FT8-Messages haben aber LIMITs:
- 3-Token-Format max 13 Zeichen pro Token
- Slash-Calls werden mit Hash-Encoding gepackt (FT8 Type 0.6 oder 1)

**Verifikations-Auftrag fuer V3:** grep `core/decoder.py` + ft8lib-Wrapper
nach wie `caller` für Slash-Calls aussieht. Wenn ft8lib bei `EA8/DA1MHH`
schon nur `DA1MHH` liefert, dann ist die DB komplett unschuldig — der
Bug ist die Decoder-Daten-Reduktion und V1 ist auf falscher Faehrte.

→ **Lesson:** vor V3 IMMER `decoder.py:_decode_message`-Output bei
echtem Slash-Call inspizieren oder Test-Sample bauen.

### L2 — Source-Truth-Kette in 3 Stufen pruefen

V1 nennt `_feed_locator_db` (mw_cycle.py:284) als Set-Punkt. Aber:
1. `decoder.py` decodiert Bytes → FT8-Message-Objekt
2. `mw_cycle._feed_locator_db` extrahiert `m.caller`+`m.field3`
3. `locator_db.set(call, locator, source)` speichert

Wenn auf Stufe 1 schon Datenverlust passiert, hilft kein Fix in 2/3.
**V3 muss die Kette von Stufe 1 bis 3 grep-verifizieren.**

### L3 — Karten-Code direction_map_widget.py:1694

V1 erwaehnt nur am Rand. Aber `_locator_db.set(rx_call, rx_loc, "psk")`
in der Karten-Update-Schleife könnte rx_call ebenfalls einen Slash-Call
sein (PSK-Reporter liefert teils komplette Calls). **AC-10 reicht nicht
als Schutz** — V3 braucht expliziten grep-Check ob Karten-Code mit
Slash-Calls funktioniert.

### L4 — `safe_locator_to_latlon` ist None-Safe — was passiert bei
ungueltigen Locatoren in der DB?

`get_position` (locator_db.py:140-148):
```python
latlon = safe_locator_to_latlon(entry.locator)
if latlon is None:
    return None
```

Gut. Aber: was wenn jemand `DA1MHH/P` mit Locator `BLABLA` reingeschmissen
hat? `safe_locator_to_latlon` returnt None → DB hat den Eintrag, aber
get_position liefert nichts. Sollte tolerabel sein, aber V3 sollte einen
Test dafuer haben.

### L5 — V1's Option C (Doppel-Lookup) hat Asymmetrie

V1 schlaegt vor: Lookup ZUERST mit komplettem Slash-Call, fallback auf
gestrippte Variante. Aber:
- `EA8/DA1MHH` (Praefix-Slash) → strip would be `EA8` (kuerzer) ODER
  `DA1MHH` (länger). Welche Strip-Logik?
- `DA1MHH/P` (Mobile-Suffix) → strip = `DA1MHH`
- `K1ABC/W2` (Region-Suffix) → strip = ???

**V1 ist hier zu vage.** Strip-Logik fuer Fallback muss explizit
spezifiziert sein.

→ **Lesson:** Strip-Heuristik klar trennen:
- Mobile-Suffix entfernen → Basis-Call
- Region-Suffix → Basis-Call (gleiche Regel)
- Praefix-Slash → KEIN strip (komplettes EA8/DA1MHH ist eigene Identitaet)

### L6 — Karten-Mobile-Suffix-Pattern in locator_db.py:180

```python
if any(call_upper.endswith(suf) for suf in MOBILE_SUFFIXES):
    prec_km = int(round(prec_km * 1.5))
```

Hier wird Mobile-Suffix erkannt aber Eintrag wird trotzdem unter
`call.upper()` (mit Suffix) gespeichert. prec_km wird verschlechtert
(*1.5). V1 hat das übersehen — beweist dass Mobile als „eigene Position"
in der DB schon designt war (nicht als Heim-Fallback).

→ **Konsequenz:** Option B (DB-Layer-Stripping) widerspricht dem
Original-Design. **Option A oder C bleiben.**

### L7 — `MOBILE_SUFFIXES` Set ist verteilt

- `ui/rx_panel.py:330` — definiert lokal
- `core/locator_db.py:13` — als Konstante (vermutlich)

V3 sollte das in EINE Quelle bringen (vermutlich `core/geo.py` oder
neue `core/callsign_utils.py`). Sonst Drift-Risiko.

### L8 — Tests bisher OHNE echte DB-Daten

V1 listet 8-10 neue Tests, aber alle mit Mock-DB. **Reicht das?**
Integration-Test mit echtem `LocatorDB`-Objekt + tmp_path-JSON-Cache
gibt mehr Sicherheit. **V3 sollte mind. 1 Integration-Test haben.**

### L9 — `callsign_to_country` Heuristik fuer Region-Suffix

V1 fragt offen: `KH6/W7XYZ` → Land KH6 oder USA? Funker-Praxis:
- Praefix-Slash `KH6/W7XYZ` → KH6 (Operator ist gerade auf Hawaii)
- Suffix-Slash `W7XYZ/KH6` → Hawaii (selber Fall, andere Notation)
- `DL/W7XYZ` → Deutschland (Operator gerade in Deutschland)

→ **Heuristik:** Bei Slash-Call mit DXCC-Praefix-Token → das ist das Land.
Mobile-Suffix (P/M/etc.) → Basis-Call entscheidet.
Region-Suffix (W2/EA8 als Suffix) → das Land ist der Suffix wenn DXCC.

DXCC-Erkennung: V3 braucht eine `is_dxcc_prefix(token)`-Helper-Funktion
oder Lookup gegen `callsign_to_country`-Tabelle.

### L10 — `_DLG_STYLE` und Konstanten-Lokalitaet

Nur Notiz: ähnliche Bugs lauern wenn Konstanten lokal definiert sind.
Keine direkte Aktion fuer P1.LOCATOR-SLASH, aber im Hinterkopf behalten.

### L11 — Test-Erwartung 888 → ~898 ist optimistisch

V1 sagt +10 Tests. Bei 4 Bugs (3 hier + Konstanten-Konsolidierung) +
DB-Audit-Script ist eher +12-15 realistisch. V3 sollte exakte Zahl
festlegen.

### L12 — APP_VERSION-Bump strittig

V1 sagt 0.95.15 → 0.95.16. Bugfix-only, kein neues Feature.
**Aber:** wenn ein DB-Audit-Helper dazukommt (Tools-Modul), das könnte
als „Feature" gelten. V3 entscheidet — vermutlich 0.95.16 (Bugfix mit
Tooling).

---

## Konsolidierte Empfehlung fuer V3

### Architektur-Entscheidung

**Option A** (strikte Trennung, kein DB-Stripping) — wegen L6 + L7.
DB-Layer bleibt stabil. rx_panel.py macht KEIN Suffix-Stripping mehr.
Lookup mit dem was Decoder geliefert hat (1:1).

→ Folge: wenn `DA1MHH/P` decoded wird und nur Heim-Eintrag `DA1MHH` in DB
ist, gibt's keinen km-Wert (Fallback Prefix-Distanz). Funker-Praxis:
das ist OK, weil Mobile-Op tatsaechlich an anderer Position ist.
Heim-Position als Default zu zeigen wäre IRREFUEHREND.

→ Alternative wenn Mike will: Option C (Doppel-Lookup) mit klarer
Strip-Logik. V3 lässt Mike entscheiden.

### Konsolidierung MOBILE_SUFFIXES

V3-Plan: zentrale Konstante in `core/geo.py` (existiert schon vermutlich
in callsign_to_country/distance — grep). Import in:
- `ui/rx_panel.py`
- `core/locator_db.py` (wenn Option B/C noch im Spiel)

### Konkreter Diff-Plan fuer V3

Annahme Option A:

1. `ui/rx_panel.py:327-335` — Slash-Logik vereinfachen:
   - Mobile-Suffix → `lookup_call = caller.split("/")[0]`
   - Sonst → `lookup_call = caller` (komplett)
2. `core/geo.py:557+` `callsign_to_distance` und `callsign_to_country`
   — `max(parts, key=len)` ersetzen durch DXCC-Praefix-Erkennung:
   - Bei Slash-Call: pro Token `is_dxcc_prefix(token)` testen
   - Erstes DXCC-Token wins als Country/Praefix-Distanz-Quelle
   - Fallback: Basis-Call
3. `core/locator_db.py` — KEINE Aenderung (Option A)
4. `tests/test_p1_locator_slash.py` — NEU 10-12 Tests
5. `tools/locator_db_audit.py` — OPTIONAL als Diagnose-Helfer

### Decoder-Verifikation

V3 MUSS Schritt 0 sein:
```bash
grep -n "caller" core/decoder.py | head -20
grep -n "_decode_message\|fields_from_msg" core/decoder.py | head -20
```
+ ein Test-Case mit gemockter Slash-Call-Message um zu sehen was
`m.caller` tatsaechlich enthaelt.

### Test-Schaetzung 12 Tests

Aufgesplittet:
- 3 Tests `_populate_row` Slash-Logik (Praefix, Mobile, Region)
- 3 Tests `callsign_to_country` Slash-Varianten
- 3 Tests `callsign_to_distance` Slash-Varianten
- 1 Test `locator_db.set/get` Konsistenz (was rein, was raus)
- 1 Test `_feed_locator_db` mit Slash-Call-Message
- 1 Integration-Test echte DB + rx_panel-Pfad

→ Tests 888 → 900 gruen.

---

## Naechste Schritte

V2 fertig. Weiter mit R1-DeepSeek-Review von V1+V2 zusammen.

R1-Prompt (fuer V3-Vorbereitung):
```
Du reviewst zwei Plans (V1 + V2) zur Behebung von 3 Slash-Call-Lookup-
Bugs in SimpleFT8. Mike's Funker-Tool, Decoder-Pfad → mw_cycle._feed_
locator_db → core/locator_db. Lookup-Pfad in ui/rx_panel.py + 
core/geo.py.

PRUEFAUFTRAG:
1. Ist die Loesungs-Empfehlung (Option A — strikte Trennung) korrekt?
   Oder fehlt ein Edge-Case der Option C/B besser machen wuerde?
2. Decoder-Verifikation als Schritt 0 — sinnvoll? Was genau pruefen?
3. DXCC-Praefix-Erkennung in callsign_to_country: gibt es bestehenden
   Code im Repo den ich nutzen kann?
4. Test-Strategie: 12 Tests reichen? Edge-Cases fehlen?
5. Risiko-Bewertung: was kann der Fix kaputt machen das aktuell
   funktioniert? (Karten-Code, Statistik, Stats-Logging?)
6. APP_VERSION 0.95.16 oder 0.95.15.x?

Antworte strukturiert mit Datei:Zeile-Referenzen.
Halte dich an SimpleFT8-Philosophie: Hobby-Tool, KISS, kein Overengineering.
```

R1-Files mitsenden:
- `prompts/p1_locator_slash_v1.md`
- `prompts/p1_locator_slash_v2.md` (diese Datei)
- `ui/rx_panel.py`
- `core/locator_db.py`
- `core/geo.py`
- `ui/mw_cycle.py` (fuer `_feed_locator_db`)
- `core/decoder.py` (fuer Decoder-Output-Verifikation)
