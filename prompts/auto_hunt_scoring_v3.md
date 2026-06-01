Du bist Senior-Entwickler für Amateurfunk-Software (Python). Projekt SimpleFT8:
Hobby-Funker-Tool für EINEN Operator (FlexRadio, FT8/FT4/FT2). KISS-Pflicht, KEIN
Contest-Tool. Wir hatten gestern eine erste Runde zum Auto-Hunt-Scoring — deine
Empfehlung "SNR-Minimum -21 dB lassen, schwaches DX nicht automatisch anrufen"
war FALSCH und der Operator hat klar widersprochen. Diese Runde korrigiert das.

================================================================================
KORREKTUR / NEUES VERSTÄNDNIS (vom Operator + Web-Recherche bestätigt)
================================================================================
Der Operator (Standort Deutschland) ist DX-Jäger. Seine Kernaussage:
  "Was helfen mir 4000 deutsche Stationen, wenn ich Falkland nie habe? Die müsste
   von der Priorität ganz oben stehen, WEIL sie so selten ist. Eine schwache
   Station zu bekommen ist doch GERADE der Sinn. Die seltensten sind — weil ich
   in Deutschland bin — meist auch die weitesten: Argentinien, Peru, Falkland,
   Japan, Korea. Das sind die Perlen."

Web-Recherche bestätigt funk-technisch:
- FT8 ist ein SCHWACHSIGNAL-Modus, dekodiert bis ~-24 dB UNTER dem Rauschen.
  Genau dafür gebaut: seltenes DX arbeiten, das auf CW/SSB unhörbar wäre.
  → Ein schwaches Signal (-24 dB) ist KEIN Ausschlussgrund, sondern der Normalfall
    für die wertvollsten Verbindungen. Der bisherige Filter `_MIN_SNR=-21`
    arbeitet GEGEN den Zweck des Modus.
- Seltenheit wird offiziell über die Clublog "Most Wanted"-Liste gemessen
  (P5 Nordkorea, Scarborough Reef, San Felix, Pratas, Kure, Johnston, Peter I,
  Kerguelen FT5, Aves, Bouvet ...). Über alle Modi aggregiert.

NEUE ZIEL-PRIORITÄT (Operator-Wille):
  Eine seltene/weite/neue Station gewinnt — AUCH wenn sie schwach ist — gegen
  jede nahe häufige Station. SNR ist nur noch Feinheit, kein K.O.-Kriterium.

================================================================================
AKTUELLES SCORING (core/auto_hunt.py, angehängt — zu ERSETZEN)
================================================================================
`select_next` Z.332–471, `_score` Z.473–493. Heute:
  - Vorfilter SNR < -21 dB → RAUS (Z.49/416)  ← MUSS WEG oder massiv gelockert
  - nie gearbeitet +3.0 / neues Band +2.0 / schon auf Band 0.0(skip)
  - SNR-Bonus +0.1*(snr+21), Bereich 0..~3.1  ← dieser große Range war der Grund,
    warum in Runde 1 dein additiver +0.7-Distanzbonus NICHT gereicht hätte
    (nahe starke Station 3.0+2.6 schlug fernes DX 3.0+0.6+0.7). Beachte das.

================================================================================
VERFÜGBARE DATEN (verifiziert im Code)
================================================================================
Pro LIVE-CQ-Station (nur Call + SNR + freq bekannt):
  - `core/geo.py: callsign_to_distance(call, my_grid) -> int|None` km (über
    Präfix→DXCC-Land-Zentrum; mein Grid aus Settings). Verifiziert: erkennt
    VP8=Falkland 13041km, LU=Argentina, OA=Peru, JA=Japan, HL=Korea, 3Y=Bouvet.
    SCHWÄCHE: Sonderpräfixe teils falsch (FT5 Kerguelen → fälschlich "Frankreich
    647km"). Für die meisten Fälle aber brauchbar.
  - `core/geo.py: callsign_to_country(call) -> str` Ländername (aus ISO-2-Code
    via Präfix-Map _PREFIX_MAP, ~340 Präfixe).
  - KEINE Call→Kontinent- und KEINE Call→CQ-Zone-Funktion vorhanden.

Aus der Historie (18k eigene QSOs, ADIF in adif/_backup_qrz_export/, wird neu beim
Start in `log/qso_log.py` geladen — separater Task):
  - bisher nur set von gearbeiteten Calls + (call,band).
  - ABLEITBAR mit geringem Aufwand: pro Land/ISO ein ZÄHLER, indem man beim Laden
    jeden historischen Call durch `callsign_to_country` jagt → dict {land: count}.
    Beispiel-Ergebnis: {"Germany": 4000, "Japan": 30, "Falkland": 0}.
    → "persönliche Seltenheit": count==0 = nie gearbeitet (Perle),
      niedrig = selten, hoch = Allerweltsland.
  Die QRZ-ADIF-Records haben auch echte DXCC-Entity-Nr / CONT / CQZ-Felder, aber
  die gibt es NUR für die Historie, NICHT für eine Live-Station — daher als
  gemeinsamer Schlüssel zwischen Historie und Live nur Land/ISO praktikabel.

================================================================================
MEIN DESIGN-VORSCHLAG (bitte kritisch prüfen + KONKRETE TABELLE liefern)
================================================================================
Lexikografische Rangordnung (Tupel-Sort, KISS — kein Gewichte-Tuning), Idee:
  1. Persönliche Seltenheit des Landes (nie gearbeitet > selten > häufig)
  2. Distanz-Klasse (weiter = besser)
  3. SNR (nur Stichentscheid)
Plus: SNR-Filter komplett raus (oder nur Boden bei ~-24 dB = FT8-Dekodiergrenze,
gegen Geister-Decodes).
Plus Prinzip-Idee: "Aufwand lohnt sich invers zur Seltenheit" — eine seltene
Perle ruft man auch bei -24 dB an; eine häufige Station nur bei gutem Signal.

================================================================================
FRAGEN AN DICH
================================================================================
F1. KONKRETE BEWERTUNGSTABELLE: Liefere eine durchdachte, KISS-taugliche
    Bewertung (Tupel-Rangordnung ODER additive Formel — du entscheidest, mit
    Begründung). Definiere die Klassen/Schwellen konkret:
      - Seltenheits-Klassen aus persönlichem count (z.B. 0 / 1-5 / 6-50 / >50?)
      - Distanz-Klassen in km (z.B. <2000 / 2000-6000 / 6000-12000 / >12000?)
      - Rolle von "neue Station (Call) auf Band" vs "neues LAND"
      - Rolle SNR
    Zeige 4-5 WORKED EXAMPLES mit Rangfolge, u.a.:
      a) Falkland VP8, nie gearbeitet, -24 dB, 13000 km
      b) neue DL-Station, +5 dB, 300 km
      c) Japan JA, 30x gearbeitet, -10 dB, 9000 km  (weit aber häufig)
      d) San Marino T7 (selten, aber NAH ~600 km), nie gearbeitet, -5 dB
      e) USA W, 200x gearbeitet, neu auf diesem Band, -8 dB, 7000 km
    Erwartung des Operators: a) ganz oben. d) soll auch hoch (selten!), obwohl nah
    — passt das mit reiner Distanz, oder MUSS persönliche Seltenheit das Leitmaß
    sein statt Distanz? Distanz ist nur ein PROXY (USA weit aber häufig; San
    Marino nah aber selten). Kläre das Spannungsfeld klar.

F2. SNR-Filter: ganz raus, oder Boden bei ~-24 dB? Geister-/Fehl-Decodes? Risiko
    Auto-Hunt ruft sinnlos ins Rauschen? Wie KISS lösen.

F3. Persönliche Seltenheit (Historie-count) vs. eingebaute statische "Most
    Wanted"-Top-Liste (z.B. Top 50 Entities hartcodiert): Aufwand/Nutzen für ein
    Hobby-Tool? Reicht persönliche Seltenheit (count==0/niedrig), oder bringt eine
    kleine eingebaute Most-Wanted-Liste spürbaren Mehrwert? Empfehlung + Warum.
    Bedenke: persönliche Seltenheit nutzt vorhandene Daten, ist personalisiert
    und braucht keine Pflege; eine Most-Wanted-Liste veraltet + braucht
    Präfix→Entity-Mapping (das wegen Sonderpräfixen wie FT5 lückenhaft ist).

F4. Slot-Affinität (heute bevorzugt Auto-Hunt gleiches tx_even, Z.437-444): bei
    DX-Jagd hinderlich? Soll eine seltene Perle den Slot-Vorzug schlagen?

F5. KLEINSTER ROBUSTER WURF: konkrete Änderungen (Datei, Funktion, ~Zeilen) für
    die volle Lösung die der Operator will (Historie-counts + neues Scoring +
    SNR-Filter raus). Was ist Phase 1 vs. optionale Spätere?

Antwort-Format: (1) kurze Einordnung, (2) F1 mit konkreter Tabelle + Worked
Examples, (3) F2-F5, (4) Severity-Tabelle 🔴/🟠/🟡/⚪ mit Datei:Zeile. Sei
konkret mit Zahlen — der Operator will eine vorzeigbare Bewertungstabelle sehen.

Angehängt: core/auto_hunt.py, log/qso_log.py.
