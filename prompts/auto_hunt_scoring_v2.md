Du bist Senior-Entwickler für Amateurfunk-Software (Python/PySide6). Projekt
SimpleFT8: ein **Hobby-Funker-Tool für EINEN Operator** (FlexRadio, FT8/FT4/FT2).

⛔ WICHTIG — PROJEKT-PHILOSOPHIE (bitte strikt einhalten):
- Das ist KEIN Contest-Tool. Zielgruppe: ein Hobby-Funker (Mike) der entspannt
  funkt. KISS schlägt Vollständigkeit. Lieber 3 gut funktionierende Regeln als
  20 konfigurierbare Gewichte die man erst lernen muss.
- Keine Contest-Features, keine komplexen Filter-Macros, kein Multiplikator-
  Gerechne wie in einem Logger. Schlag NICHTS in diese Richtung vor.
- Mike ist DX-interessiert: er will, dass das Auto-Hunt-Feature (ruft
  automatisch CQ-Stationen an) **seltene/weite/neue** Stationen bevorzugt
  statt der 100. nahen Europa-Station.

Deine Aufgabe: ZUERST DIAGNOSE auf Basis des Codes (nicht meiner Worte folgen,
sondern im Code nachweisen), DANN ein KISS-Design für ein verbessertes
Auto-Hunt-Scoring. Belege jede Aussage mit Datei:Zeile.

================================================================================
IST-ZUSTAND (verifiziert)
================================================================================
Auto-Hunt (`core/auto_hunt.py`) wählt jeden Decode-Zyklus EINE CQ-Station zum
automatischen Anrufen. Pipeline in `select_next` (Z.332–471):

1. Vorfilter pro Kandidat:
   - nur `is_cq`
   - gültiges Rufzeichen (`looks_like_callsign`)
   - Recent-QSO-Cooldown 30 Min (`_RECENT_QSO_COOLDOWN_S=1800`, Z.60)
   - Fail-Cooldown 5 Min (`_COOLDOWN_SECS=300`)
   - **SNR-Minimum `_MIN_SNR=-21` dB (Z.49)** → schwächere Signale fallen RAUS
2. Slot-Affinität (Z.437–444): bei laufender Session bevorzugt gleiches tx_even.
3. Scoring `_score` (Z.473–493):
   - nie gearbeitet:            +3.0  (`_W_NEW_STATION`)
   - gearbeitet, nicht auf Band:+2.0  (`_W_NEW_BAND`)
   - schon auf Band gearbeitet:  0.0  → übersprungen
   - SNR-Bonus: +0.1 * max(0, snr+21)  (`_W_SNR`)
4. `candidates.sort(key=score, reverse=True)`, bestes Element gewinnt (Z.451).

Worked-Before-Quelle (`log/qso_log.py`): set von Base-Calls + (call,band)-Tupeln.
Geladen in `ui/main_window.py:_init_qso_log` (Z.232) NUR aus: `Path.cwd()`,
`adif_import_path` (Settings), `adif/hochgeladen/`.

================================================================================
MIKES ZWEI PRAXIS-PROBLEME (Field)
================================================================================
PROBLEM A — Historie fehlt:
Mike hat ~18.000 reale QSOs mit seinen Calls DA1MHH + DO4MHH, die als ADIF im
Ordner `adif/_backup_qrz_export/` liegen (2 Dateien, ~19 MB). Diese werden NICHT
ins qso_log geladen → Auto-Hunt hält längst gearbeitete Stationen für "neu"
(+3.0) und ruft sie wieder an. (Derselbe QRZ-Export wird vom Diplome-Feature
`core/awards.py` bereits on-demand geladen — Felder dort: DXCC[Entity-Nr], CONT,
STATE, CQZ, LOTW_QSL_RCVD, CALL, BAND.)

PROBLEM B — DX verliert immer:
Mike empfängt z.B. Falkland-Inseln mit -24 dB. Er ruft sie NIE an, weil:
  (b1) -24 dB < _MIN_SNR(-21) → Station wird gar nicht erst Kandidat.
  (b2) Selbst wenn: eine nahe NEUE Europa-Station hat +3.0 plus hohen SNR-Bonus
       und schlägt das seltene, schwache DX. Entfernung und Seltenheit des
       Landes/Kontinents fließen NICHT ins Scoring ein.

Mike will: weite Distanz + seltenes Land/seltener Kontinent sollen ein DX nach
oben ziehen, damit er nicht nur Europa abtelefoniert.

================================================================================
VERFÜGBARE BAUSTEINE (im Code vorhanden, wiederverwendbar)
================================================================================
`core/geo.py`:
  - `callsign_to_distance(call: str, my_grid: str) -> int|None`  (Z.606)
      Entfernung in km, über Präfix→DXCC-Land-Zentrum (braucht KEIN Grid der
      Gegenstation; mein eigener Grid kommt aus Settings).
  - `callsign_to_country(call: str) -> str`  (Z.638)  → Ländername (aus ISO-Code).
  - `_PREFIX_MAP` (Z.156): Präfix → ISO-2-Code (DE, NL, FR, GB, ...).
  - `grid_distance(my_grid, dx_grid) -> int|None` falls Grid vorhanden.
  Es gibt KEINE Call→Kontinent- und KEINE Call→CQ-Zone-Funktion. Kontinent/Zone
  pro LIVE-Call wären also neu zu bauen (z.B. ISO→Kontinent-Map).

`core/awards.py`: `compute_awards(records)` → pro Diplom worked-Sets (DXCC-Nrn,
CONT, STATE, CQZ) aus ADIF-Records.

================================================================================
DATEN-BRUCH (zentrale Design-Frage)
================================================================================
Der QRZ-Export liefert für VERGANGENE QSOs DXCC-Nr / CONT / CQZ. Eine LIVE-CQ-
Station liefert nur ihren Call → via geo.py einen ISO-2-Ländercode (DE, GB...).
Für "habe ich dieses LAND/diesen KONTINENT schon?" muss ich beide Welten auf
EINE gemeinsame Schlüssel-Ebene bringen. ISO-Code ist die einzige Ebene die für
Live-Calls überhaupt verfügbar ist. Frage: wie "worked countries/continents" als
ISO-Code-Sets gewinnen — DXCC-Nr→ISO mappen (Tabelle ~340 Einträge, Pflegelast)
oder die gearbeiteten Calls durch `callsign_to_country` jagen (billiger, aber
ungenau bei Slash/Sonderpräfixen)? Oder Land/Kontinent-Seltenheit ganz weglassen
und nur reine Distanz nehmen (KISS)?

================================================================================
FRAGEN AN DICH (bitte konkret + KISS beantworten)
================================================================================
F1. Scoring-Architektur: aktuell rein additive Gewichte. Wenn ich Distanz +
    Seltenheit dazunehme — wie verhindere ich, dass eine Dimension alles
    dominiert? Empfiehlst du weiter additiv (mit welcher Normalisierung der km?),
    eine kleine Anzahl Tiers (z.B. Distanz-Klassen: <2000/2000-8000/>8000 km),
    oder lexikographisch (erst Neuheit, dann Distanz, dann SNR)? Begründe für ein
    Hobby-Tool.

F2. Problem B / SNR-Minimum: muss `_MIN_SNR` für weites DX gelockert werden?
    Trade-off: -24 dB DX ist anrufbar aber die Erfolgswahrscheinlichkeit
    (decodiert die Gegenstation MICH?) ist gering. Wie balancieren — z.B.
    SNR-Minimum nur für Stationen jenseits einer Distanzschwelle absenken? Oder
    bleibt es bei -21 und Mike ruft -24 dB bewusst von Hand an? Was ist KISS-
    richtig für einen Hobby-Funker der Frust ("ich ruf nur Europa") vermeiden,
    aber nicht stundenlang erfolglos schwaches DX jagen will?

F3. Distanz-Gewicht: linear km, log(km), oder Distanz-Klassen? Welche
    Größenordnung relativ zu +3.0 (neu) und SNR-Bonus, damit ein neues fernes DX
    eine nahe neue Europa-Station schlägt, aber ein bereits gearbeitetes fernes
    DX NICHT ein neues nahes schlägt (Neuheit soll Leitkriterium bleiben)?

F4. Seltenheit Land/Kontinent: lohnt sich der Daten-Brücken-Aufwand (DXCC↔ISO)
    für ein Hobby-Tool, oder ist "neu + Distanz" schon 90% des Nutzens? Wenn ja
    zu Seltenheit: welcher minimal-invasive Weg (welche Datenquelle, welcher
    Schlüssel)? Was würdest du in Phase 1 WEGLASSEN?

F5. Problem A (Historie laden): reicht es, `adif/_backup_qrz_export/` in
    `_init_qso_log` zusätzlich per `load_directory` zu laden? Risiken: Ladezeit
    beim Start (19 MB ADIF, ~18k QSOs, parse_adif_file), Speicher, Dubletten mit
    `adif/`. Ist Lazy/Caching nötig oder ist Eager-Load beim Start ok? Beachte:
    die Diplome laden denselben Export bereits on-demand — sollte qso_log das
    teilen statt doppelt zu parsen?

F6. Was ist der KLEINSTE Wurf (Phase 1), der Mikes beide Probleme spürbar löst,
    ohne Overengineering? Skizziere die konkreten Änderungen (Datei, Funktion,
    ~Zeilen) und was bewusst in eine spätere Phase 2 verschoben wird.

Sicherheit (nur zur Info, nicht dein Fokus): TX läuft IMMER über ANT1 — Scoring
ändert nur WELCHE Station gerufen wird, nicht die Sendeantenne. Kein HW-Risiko.

FORMAT: (1) Diagnose-Abschnitt (bestätige/korrigiere meine Befunde mit
Datei:Zeile), (2) Antworten F1–F6, (3) Tabelle: Schwere | Empfehlung |
Datei:Zeile | Begründung. Severity: 🔴 Bug / 🟠 Risiko / 🟡 Verbesserung / ⚪ Hinweis.

Angehängt: core/auto_hunt.py, log/qso_log.py, core/awards.py.
