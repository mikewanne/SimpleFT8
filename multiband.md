# Multiband — Brainstorm / Konzept

> **Status:** Konzept vollständig + DeepSeek-geprüft (Urteil: Umsetzung
> empfohlen) — KEIN Spec, KEIN Code, noch keine Umsetzungs-Entscheidung.
> Erstellt: 2026-05-22 (Mike + Claude).
> **Erweitert 2026-06-03:** Auto-Hunt-Architektur bei zwei Bändern geklärt +
> ein zweites Mal DeepSeek-gehärtet (1 🔴 Blocker gefunden) — siehe Abschnitt
> „Auto-Hunt bei zwei Bändern" am Ende.

---

## Grundidee (Mike, 2026-05-22)

Eine Funktion **Multiband**, die man bewusst aktiviert. Ablauf:

1. Multiband einschalten.
2. Zwei Bänder auswählen — Beispiel: **20m + 15m**.
3. Multiband starten.
4. Beim Start wird **einmalig kalibriert**:
   - TUNE + Gain auf 20m → Werte speichern
   - TUNE + Gain auf 15m → Werte speichern
5. Die gespeicherten Werte sind **6 Stunden gültig**.
6. Danach läuft der Bandwechsel **nicht mehr** über die reguläre,
   langsame Prozedur (live messen), sondern **direkt aus den 6h-Cache-
   Werten** → schnelles Umschalten.

**Kerngedanke:** Den teuren Teil (TUNE + Gain messen) einmal vorab für
beide Bänder erledigen. Danach ist Bandwechsel nur noch „Werte laden",
nicht „Werte messen".

---

## Physikalische Basis (geklärt 2026-05-22)

- Eine **SCU** erfasst den kompletten KW-Bereich auf einmal — über die
  gerade aktive Antenne (ANT1 **oder** ANT2, nie beide gleichzeitig).
- Ein **Slice** schneidet daraus ein schmales Fenster (~3 kHz bei FT8).
- Der **8400M hat 2 Slices** → zwei solcher Fenster gleichzeitig nutzbar.
- **Diversity kostet keinen Slice.** Sie ist das zeitliche Umschalten der
  einen Antenne auf SCU-Ebene (even-Slot ANT1, odd-Slot ANT2). Beide
  Slices fahren automatisch mit — egal welche Antenne gerade dranhängt.
- **FT8-Slots sind global UTC-synchron** — even/odd ist auf beiden
  Bändern derselbe Takt. Basis für die Slot-Logik beim Senden (Fall A/B).

→ Folge: Zwei Bänder gleichzeitig empfangen UND Diversity behalten wäre
physikalisch möglich — die *Design-Entscheidung* dagegen (Multiband ohne
Diversity) steht im Abschnitt „Antennen-Modell".

---

## Was im Projekt schon existiert (hilft bei der Umsetzung)

Vieles vom „Pro-Band-Wert speichern" ist bereits gebaut:

- **TUNE-Stützpunkt pro Band** — `RFPresetStore` (P54): 10-W-Stützpunkt
  je Band für schnellere TX-Power-Konvergenz.
- **Unified Gain Store** — `~/.simpleft8/kalibrierung/presets.json`
  (P80): eine Gain-Messung pro Band, modus-übergreifend.
- **DT-Korrektur pro Band+Modus** — `dt_corrections.json`.
- **TX-Power pro Band** — `settings.get/save_tx_power(band)`.
- **Diversity-Ratio pro Band+Modus** — `presets_standard.json` /
  `presets_dx.json`.
- **Verfalls-Logik** — P83 „noch X Stunden bis Re-Mess" + Stale-Anzeige.
- **2. Slice + 2. Audio-Stream** — `radio/flexradio.py` enthält bereits
  die Mechanik für einen zweiten Slice mit eigenem DAX-Kanal, RX-Stream
  und Audio-Callback (`enable_diversity`, `on_audio_callback_b` u.a.).
  Aktuell **toter Code** (kein Aufrufer — siehe TODO.md), aber genau die
  Plumbing, die Multiband für das zweite Band braucht. → Wird Multiband
  gebaut, wird dieser Code **adaptiert statt gelöscht**.

→ Der „6h gültige Werte je Band"-Mechanismus müsste also kein neues
System sein, sondern könnte auf den vorhandenen Stores aufsetzen.

---

## Bänderauswahl & Empfang (geklärt 2026-05-22, verfeinert 2026-05-23)

- **Empfang läuft auf beiden gewählten Bändern gleichzeitig** — Slice A
  z.B. dauerhaft 20m, Slice B dauerhaft 15m. Beide laufend dekodiert,
  beide Stationslisten zusammen im RX-Fenster.

- **Band-Buttons sind 3-stufige Cycle-Schalter**, maximal 2 Bänder
  gleichzeitig aktiv (= die 2 Slices des 8400M):

  | Stufe | Bedeutung | Visual |
  |---|---|---|
  | **OFF** | nicht empfangen, kein TX | grau/dunkel |
  | **RX** | wird mitempfangen + dekodiert, kein TX | blau (normal) |
  | **TX** | empfangen + dekodiert + **CQ/Hunt laufen hier** | blau, kräftig leuchtend |

  **Klick-Zyklus:** OFF → RX → TX → OFF.

- **Constraint: immer genau ein TX-Band.** Wird Band B auf TX gehoben,
  wird das bisherige TX-Band (A) automatisch auf RX demotet — nicht
  abgeschaltet, nur „nicht mehr TX". Die Frequenzanzeige springt mit.

- **App-Start:** 20m steht direkt auf TX (= einzige aktive Band).

- **Auto-Promote bei nur einem verbleibenden Band:** Wenn das TX-Band
  auf OFF gecycled wird und es ist noch ein RX-Band aktiv → das
  RX-Band promotet automatisch auf TX. Verhindert den unsinnigen
  „nichts TX-aktiv"-Zustand.

- **Klick auf ein 3. Band bei schon 2 aktiven → ablehnen.** Der User
  muss erst eines der beiden bewusst auf OFF cyclen, dann ist der
  Slice frei. **Begründung Mike 23.05.:** nicht riskieren das falsche
  Band zu verdrängen — vielleicht steht da gerade die Nordkorea-Station,
  besser explizit deaktivieren als automatisch ersetzen.

- **Beispiel-Durchlauf:**
  - Start → 20m=TX
  - Klick 15m → 20m=TX, 15m=RX (beide dekodiert)
  - Klick 15m → 20m=RX, 15m=TX (Freq-Anzeige hüpft auf 15m,
    CQ/Hunt läuft jetzt dort)
  - Klick 15m → 15m=OFF, 20m=TX (Auto-Promote)

- **Warum 3 Stufen statt 2:** löst das Pain-Point „TX-Band wählen ohne
  vorher eine Station anklicken müssen". CQ und Auto-Hunt können jetzt
  explizit auf einem Band gestartet werden, indem man dieses auf
  Stufe TX cycled — keine Krücke „Station klicken nur damit TX-Band
  umspringt".

## RX-Fenster — Anzeige & Band-Filter (geklärt 2026-05-22)

**Anzeige: eine gemeinsame Stationsliste mit farbcodierter Band-Spalte**
— nicht zwei getrennte Fenster mit Slider.
- Der Platz verteilt sich von selbst: Band mit vielen Stationen kriegt
  viele Zeilen, Band mit wenigen wenige — kein Slider-Gefummel.
- Jede Station trägt eine farbige Band-Markierung (20m eine Farbe, 15m
  eine andere) — passt zum Farb-Coding-Stil der App.
- KISS: eine Liste statt zwei Panes + Splitter + Drag-Logik.

**Band-Filter (2 Buttons, oben neben dem Frequenz-Filter):**
- Zwei Buttons, beschriftet mit den 2 aktiven Bändern (z.B. „15M",
  „20M"). Farbe zeigt den Filter-Zustand.
- Drei Zustände, **nie beide rot** (beide aus = leeres Fenster):
  - Beide grün → beide Bänder sichtbar (Default).
  - Einer rot / einer grün → nur das grüne Band sichtbar.
- Logik:
  - Grünen Button drücken, anderer ist grün → gedrückter wird rot
    (Band ausgeblendet).
  - Grünen Button drücken, anderer ist schon rot → **Wechselschaltung**:
    der rote wird grün, der gedrückte wird rot (sichtbares Band wird
    getauscht).
  - Roten Button drücken → wird grün (Band wieder einblenden).
- Die Buttons sind reine **Ansichts-Filter** — getrennt von der
  Band-*Auswahl* (welche 2 Bänder aktiv sind). Wird ein Band getauscht,
  werden die Buttons neu beschriftet, beide grün.

**Hinweis zum Stand der Technik:** Eine integrierte „zwei Bänder, ein
Fenster, Klick zum Arbeiten"-Lösung gibt es in keiner Mainstream-FT8-
Software. SparkSDR kommt am nächsten (Multiband-Decode+TX, Windows,
eher Skimmer), CWSL_DIGI ist reines Skimmen. Sonst: separate WSJT-X-
Instanzen pro Band. Multiband füllt damit eine echte Lücke.

## Antennen-Modell (geklärt 2026-05-22)

**Multiband läuft OHNE Diversity — feste Antenne ANT1 für RX und TX.**

Begründung:
- Diversity-Ratio ist pro Band optimiert; bei zwei Bändern auf einer
  geteilten SCU-Antennen-Zeitachse läuft nur ein Kompromiss-Muster →
  Nutzen verwässert.
- Diversity bräuchte ANT1/ANT2-Messung + Ratio für **beide** Bänder →
  bläht den Start auf, Gegenteil von „schnell".
- KISS: Multiband = „zwei Bänder, ein Knopf, einfach".
- TX ist ohnehin ANT1 → fester RX auf ANT1 = null Antennen-
  Entscheidungen, kein Umschalten, kein Messen.

→ **Multiband und Diversity sind zwei getrennte Modi.** Man wählt einen:
Diversity = ein Band, maximale Ausbeute. Multiband = zwei Bänder im
Blick, einfach. Multiband-Start braucht nur TUNE + Gain je Band.

## Senden — Bandsprung & Slot-Timing (Mike, 2026-05-22)

Ausgangslage: Puffer feuert (laufendes QSO beendet), Ziel-Station z.B.
Nordkorea auf 15m. Sie sendet in ihren Slots (z.B. odd), wir antworten
im Gegen-Slot (even). **Zwei Fälle — je nachdem ob das Band schon
getunt ist:**

**Wann tritt Fall B (Band nicht getunt) überhaupt ein?** Normalerweise
wird ein Band schon beim Hinzufügen ins Paar getunt (F4). Fall B greift
nur, wenn der TUNE noch aussteht — Band während eines QSOs hinzugefügt
(TUNE aufgeschoben) oder die 6h sind abgelaufen.

### Fall A — Zielband ist getunt
Gain/Leistung/RF liegen aus dem 6h-Cache sofort vor, ATU recallt die
gespeicherte Lösung (F2). Reine Rechenfrage „reicht die Restzeit?":
- **Genug Restzeit** zum Umschalten → im nächsten even-Slot antworten.
- **Zu wenig Restzeit** (Richtwert ~3 s, Feld-Parameter) → übernächster
  even-Slot.

### Fall B — Zielband ist NICHT getunt
- **Immer den ersten even-Antwort-Slot überspringen** — ohne
  Zeitrechnung, egal wieviel Restzeit ist.
- Das **Umschalten** (TX-Flag, Werte setzen) passiert in der Restzeit
  von Nordkoreas odd-Slot — keine Sendung, jederzeit möglich.
- Der **TUNE-Träger** wird in den übersprungenen even-Slot gelegt
  (= der freie TX-Slot für den TUNE).
- Nordkorea sendet im nächsten odd-Slot erneut (ihr Rhythmus läuft).
- Wir antworten im darauf folgenden even-Slot.
- Zeitfenster großzügig (~25–30 s gesamt: odd-Rest + übersprungener
  even-Slot) — ein TUNE braucht nur wenige Sekunden, passt locker.

In beiden Fällen bleibt die **Parität** erhalten (Antwort immer im
Gegen-Slot der Station). Fall B kostet schlicht einen Antwort-Zyklus
für den TUNE.

## QSO-Verhalten beim Band-Klick (geklärt 2026-05-22)

Szenario (Mike): QSO mit Österreich auf 20m läuft — plötzlich erscheint
Nordkorea auf 15m. Klick drauf. Was passiert?

**Entscheidend: Ist ein echter, beidseitiger Kontakt zustande gekommen?**

- **Laufendes QSO** (Gegenstation hat geantwortet, Austausch läuft) →
  Klick wird **gepuffert**. Popup „QSO läuft" — die geklickte Station
  wird **automatisch gerufen, sobald das laufende QSO sauber beendet
  ist**. Ein laufendes QSO abbrechen wäre „einen Freund sitzen lassen" —
  moralisch nicht OK.
- **CQ-Ruf läuft** (du rufst CQ, niemand engagiert) → Klick → **sofort
  abbrechen + Band wechseln**. CQ ist keine Verpflichtung.
- **Du rufst eine Station, sie hat noch nicht geantwortet** (kein
  Kontakt zustande) → Klick → **sofort abbrechen + Band wechseln**.
  Noch kein QSO, keine Verpflichtung.

Die Grenze: Sobald die Gegenstation dir geantwortet hat → echtes QSO →
gepuffert. Davor (CQ oder unbeantworteter Anruf) → frei zum Wechseln.

**Ein QSO zur Zeit.** Kein paralleles QSO auf beiden Bändern (wäre
Contest-Gehetze, widerspricht KISS). Das andere Band läuft während eines
QSOs als reiner Beobachter weiter und dekodiert sichtbar mit.

## Der eine Sender — TX als geteilte Ressource (geklärt 2026-05-22)

**Das Radio hat genau einen Sender.** TUNE, FT8-TX auf Band A und
FT8-TX auf Band B konkurrieren alle um dieselbe eine PA. Ein TUNE ist
ein Sende-Vorgang (Träger) → er kann nicht gleichzeitig mit einem
FT8-QSO laufen.

**Auflösung — RX ist frei, TX wird serialisiert:**

- **Empfang braucht keinen Sender.** Ein neu hinzugefügtes Band fängt
  **sofort** an zu dekodieren — Stationen sind direkt sichtbar. Der
  TUNE betrifft nur das *Senden* auf dem Band.
- **TUNE wird in einen freien TX-Slot eingeplant:**
  - App ist idle → TUNE im nächsten TX-Slot, erledigt.
  - App ist in einem QSO → TUNE wird **aufgeschoben bis das QSO
    beendet ist**. Das QSO hat Vorrang.
- **Klick auf eine Station auf noch nicht getuntem Band** → läuft über
  die bestehende Puffer-Logik: Klick wird gepuffert, bei QSO-Ende
  zuerst TUNE, dann Anruf der Station.
- **Startup:** die 2 gewählten Bänder werden nacheinander getunt
  (~2 TX-Slots), dann Betrieb. Kein QSO aktiv → unkritisch.

**Prinzip:** Empfang ist sofort und kostenlos. Alles was den Sender
braucht — TUNE, FT8-TX — wird serialisiert; ein laufendes QSO hat
immer Vorrang.

---

## Bekannte Grenzen (geklärt 2026-05-22)

- **Jeder TX-Slot kostet auch das andere Band einen Slot.** Es gibt
  einen Sender, und TX blockt RX — sendest du FT8 (oder einen TUNE) auf
  Band A, dekodiert in dem Slot auch Band B nicht. Über ein QSO
  (~5 TX-Slots) verliert das andere Band ein paar Slots. Unkritisch —
  FT8-Stationen wiederholen sich; nur zu wissen.
- **Doppelte Decoder-Last** — zwei Bänder pro Slot dekodiert. Für einen
  aktuellen Mac problemlos.

---

## Design-Entscheidungen (F1–F7)

### F1 — Empfangs-Modell ✅ GEKLÄRT
Echtes Dual-RX: beide Bänder dauerhaft auf je einem Slice, laufend
dekodiert. Senden = ein Band zur Zeit, Sprung auf das geklickte Band.
Siehe Abschnitte „Bänderauswahl & Empfang" + „Senden" oben.

### F2 — Bandsprung beim Senden ✅ weitgehend GEKLÄRT (2026-05-22)

**Kein Slice-Umstimmen nötig** — beide Slices laufen permanent auf
beiden Bändern. Der TX-Bandsprung ist nur:
1. TX-Flag auf den Slice des Zielbandes (`slice set X tx=1`) — TCP-
   Befehl, Millisekunden.
2. Leistung + Gain aus 6h-Cache setzen — TCP-Befehle, Millisekunden.
3. ATU recallt **automatisch** die gespeicherte Lösung des Bandes.

**ATU-Fakten (FlexRadio-Doku):** Der 8400-Tuner ist relais-basiert,
Recall gespeicherter Lösungen „effektiv sofort". Auto-Recall sobald die
TX-Frequenz nahe einer gespeicherten Lösung ist. Lösungen pro Band +
pro Antennenport gespeichert. Kein exakter ms-Wert publiziert, aber
Relais-Schalten = weit unter 1 s.

→ **Realistischer Gesamt-Switch: deutlich unter 1 Sekunde.**

**Folge für den Vorlaufzeit-Schutz:** Das echte Fenster zwischen Decode-
fertig (~13 s in den Slot — Signal endet 12,64 s) und nächstem Slot ist
~2 s. Bei Switch < 1 s reicht das. Die Schwelle von ~7–8 s ist sehr
konservativ — realistisch ~3 s. Genauer Wert = Feld-Parameter.

**Caveat (→ F4):** gilt nur bei vorhandener gespeicherter ATU-Lösung.
Cache leer/abgelaufen → ATU-Vollsuche = mehrsekündiger 10-W-Tune-Träger.
Startup-Kalibrierung (TUNE je Band) ist deshalb Pflicht.

### F3 — Diversity bei zwei Bändern ✅ GEKLÄRT
Multiband läuft ohne Diversity, feste Antenne ANT1. Siehe Abschnitt
„Antennen-Modell" oben. Diversity bleibt ein eigener, getrennter Modus.

### F4 — Kalibrierwerte & 6h-Verfall ✅ GEKLÄRT (2026-05-22)

**TUNE und Gain werden bewusst unterschiedlich behandelt:**
- TUNE = TX-Sicherheit, **Pflicht** (hohe SWR → Schutzschaltung,
  Hardware-Risiko). Nicht überspringbar.
- Gain = RX-Optimierung, hat brauchbaren Default. Überspringbar.

**TUNE — Leistung & Frequenz (Code-verifiziert 2026-05-22):**
- TUNE nutzt die **konfigurierte Tune-Leistung** aus den Einstellungen
  (TUNE-GroupBox „TX & Schutz", aus P63/P73-A) — konsistent mit dem
  manuellen TUNE.
- TUNE **nicht im FT8-Segment** (Dauerträger dort QRMt alle Decoder —
  auch bei 10 W). **Bereits in der App gelöst:** `TUNE_FREQS`-Map in
  `config/settings.py:27` → −2 kHz neben dem FT8-Segment (20m: FT8
  14.074 → Tune 14.072). Manueller TUNE (`_tune_start`) und Auto-Tune
  bei Bandwechsel holen die Frequenz beide über
  `get_tune_freq_mhz(band, mode)`, schalten den VFO kurz dorthin und
  stellen danach zurück. **Multiband verwendet dieselbe Funktion** —
  nichts Neues zu bauen.
- Ausnahme **60m**: kein Offset-Eintrag (kanalisiertes Band — ein
  Offset könnte aus einem erlaubten Kanal fallen), TUNE bleibt auf der
  Arbeitsfrequenz. Vermutlich Absicht, kein Bug.

**TUNE — Auslösung:**
- Wird ausgelöst, **sobald ein Band ins Multiband-Paar aufgenommen
  wird** (bewusste User-Aktion — beim Start die 2 gewählten Bänder,
  mid-session ein neu hinzugefügtes). **Nicht erst beim ersten TX.**
- Folge: Sieht der User später eine Station auf dem Band und klickt
  sie an, ist das Band längst getunt → Sprung instant (F2). Das „doof
  wenn gerade Nordkorea läuft"-Problem entfällt — getunt wird beim
  bewussten Band-Hinzufügen, nicht im Pileup.
- ATU-Memory bleibt **im Radio gespeichert, sessionübergreifend** — ein
  früher schon getuntes Band recallt sofort; nur ein nie getuntes Band
  kostet die mehrsekündige Suche.
- 6h-Verfall: nach Ablauf Re-TUNE bei nächster ruhiger Gelegenheit
  (nicht während eines QSOs). Der bestehende **SWR-Watchdog** erzwingt
  ohnehin einen Re-TUNE bei schlechter SWR (Sicherheitslogik ist da).

**Gain:**
- **Keine automatische Gain-Messung** — sie blockiert die UI mehrere
  Sekunden, gehört nicht in den Mid-Session-Pfad.
- Ohne Messung → **Default** (bestehender Per-Band-Wert, ~10 dB).
  Reicht für FT8-Decodierung.
- **Manuelle Gain-Messung** jederzeit per Knopf. Einmal gemessen → 6h
  gecacht und wiederverwendet. Wer's optimal will, misst manuell.

### F5 — Hardware-Sicherheit ✅ GEKLÄRT
TX läuft **immer** über ANT1 — auch beim Bandsprung. Der TUNE pro Band
ist ein ANT1-Vorgang. Im Antennen-Modell verankert (ANT1 fix für RX+TX).
Bei der Umsetzung: vor jedem TX-Trigger `set_tx_antenna("ANT1")`
verifizieren (CLAUDE.md-Hardware-Warnung).

**SWR-Überwachung:** Multiband erbt den **SWR-Watchdog des Normal-Modus**
(P63) — jeder TX wird überwacht. Der Watchdog ist bereits band-bezogen
(`_swr_blocked_bands` pro Band): schlechte SWR auf 15m sperrt 15m, 20m
bleibt nutzbar.

**Kein TX vor gültigem TUNE:** Läuft der 6h-Tune eines Bandes ab oder
fehlt er, muss der erste TX auf dem Band wieder ein TUNE sein (Fall B).
Harte Regel — notfalls TX-Verweigerung, bis getunt ist. Verhindert TX
mit hoher SWR (DeepSeek-Review-Finding).

### F6 — Projekt-Philosophie ✅ (Leitlinie)
SimpleFT8 ist ein Hobby-Tool, kein Contest-Tool. „Zwei Bänder im Blick,
Klick zum Arbeiten" ist hobby-tauglich („20m tot, 15m offen — sehe ich
sofort"). Multiband bleibt einfach — 2 Bänder, ein Knopf, kein komplexes
Setup. Gilt als Leitlinie für alle weiteren Detail-Entscheidungen.

### F7 — Puffer-Detailfragen ✅ GEKLÄRT (2026-05-22)

**Ein Puffer-Platz, letzter Klick gewinnt.**
- Genau ein Puffer-Platz. Klick auf eine weitere Station bei belegtem
  Puffer → Puffer wird **überschrieben** (z.B. erst Nordkorea gepuffert,
  dann Südkorea geklickt → Südkorea steht im Puffer). KISS.
- **Statusleiste zeigt den Puffer an:** `Puffer: <Rufzeichen>`, solange
  etwas gepuffert ist.

**Verschwundene Puffer-Station:**
- Geprüft wird **zum Zeitpunkt, an dem der Puffer feuern würde**
  (laufendes QSO ist beendet) — nicht nagelnd während des QSOs. Nutzt
  das vorhandene 2-Min-Aging des RX-Fensters: Station beim QSO-Ende
  nicht mehr in der Live-Liste → verschwunden.
- Station noch da → Bandsprung + Auto-Anruf.
- Station weg → **Info-Zeile** „<Rufzeichen> nicht mehr erreichbar —
  Anruf verworfen", Puffer gelöscht, **App bleibt auf dem bisherigen
  Band** — fertig. **Kein Bandwechsel, keine Ja/Nein-Rückfrage** — in
  Multiband sind beide Bänder ohnehin dauerhaft sichtbar, ein Wechsel
  ohne Ziel-Station hätte keinen Nutzen.
- Mitteilungen generell als **Info-Zeile**, nicht als modaler Dialog
  (unterbricht den Betrieb nicht).

---

## Review-Klärungen (OF1–OF4) — geklärt 2026-05-22

### OF1 — Betriebsart ✅
**Beide Bänder immer derselbe Modus** (beide FT8 oder beide FT4) —
gemischte Modi gibt es nicht, sonst kein KISS mehr (zwei Slot-Raster).
**FT2 ist nicht dabei** — kürzeste Slots (3,8 s) und der FT2-Decoder ist
ohnehin noch experimentell.
**Decode-Timing:** Beide Bänder werden pro Slot *nacheinander* dekodiert
(`ft8_lib`, C — sehr schnell, Bruchteile einer Sekunde je Band). Das
passt in den 15-s-FT8-Slot wie in den 7,5-s-FT4-Slot locker. Keine
parallele Dekodierung nötig.

### OF2 — Einordnung als Betriebsart ✅ (revidiert 2026-05-23)
**Multiband ist eine Erweiterung des Normal-Modus + zweites Band**, und
**Auto-Hunt und OMNI-CQ sind in Multiband verfügbar** (revidiert
2026-05-23 — ursprüngliche Empfehlung „Diversity-vorbehalten" war zu
restriktiv).

- **OMNI-CQ** im Multiband: läuft auf dem **aktuellen TX-Band** (Band
  auf Stufe TX im 3-Stufen-Cycle, siehe „Bänderauswahl & Empfang").
  User wählt das TX-Band explizit per Klick. Alternierende Variante
  (β: even-A, odd-B) verworfen — zu komplex für KISS.
- **Auto-Hunt** im Multiband: der Such-Pool umfasst beide aktiven
  Bänder, jeder Pick führt zum entsprechenden Band-TX (Fall A/B, plus
  implizite TX-Band-Promotion analog Station-Klick). Die bestehende
  Cooldown- und Worked-Vermeidung sind band-bezogen — passt ohne
  Anpassung.

Es gilt weiter: ANT1 fix, keine Diversity, ein QSO zur Zeit.

### OF3 — Aktivierung ✅ (geschärft 2026-05-23)
Multiband wird durch **erneuten Klick auf den Normal-Button** ausgelöst
— der Normal-Button wird dann zu „Multiband" (Toggle Normal ↔
Multiband, analog OMNI-CQ-Aktivierung). Das aktuelle Band wird Band 1,
Band 2 wählt der User.

**App-Start (geschärft 2026-05-23): immer 20m + FT8 (Normal).** Das
bisherige Speichern und Laden von Band/Modus wird **vollständig
entfernt** — die App startet bei jedem Start in 20m FT8. Multiband-
State auch nicht persistiert.

### OF4 — Frequenzanzeige & TX-Band-Indikator ✅ (erweitert 2026-05-23)
Zeigt das aktuelle TX-Band, aktualisiert sich beim Bandsprung
(Farbcodierung wie bisher).

**Zwei sichtbare TX-Band-Indikatoren in Multiband:**
- **Frequenzanzeige** — groß, prominent, nicht zu übersehen.
- **Band-Selector-Button** — das TX-Band leuchtet kräftiger blau als
  die anderen aktiven Bänder (Stufe TX vs Stufe RX im 3-Stufen-Cycle,
  siehe „Bänderauswahl & Empfang").

**TX-Band wird gesetzt durch:**
- **Explizit** per Band-Selector-Cycle (Klick auf RX-Band → TX-Band).
  Das ist der Hauptweg für CQ/OMNI/Auto-Hunt auf einem Band ohne
  vorherige Station-Auswahl (verfeinert 23.05.).
- **Implizit** durch Station-Klick (Klick auf 15m-Station → TX springt
  auf 15m, bisheriges TX-Band demotet auf RX).
- **Implizit** durch Auto-Hunt-Pick (analog Station-Klick).
- **Implizit** durch Auto-Promote, wenn nur noch ein aktives Band
  übrig ist.

Die **Band-Filter-Buttons** im RX-Fenster-Header (oben neben Freq-
Filter, siehe „RX-Fenster") sind davon getrennt — sie steuern nur die
DISPLAY-Sichtbarkeit der Stationen in der Liste, nicht den RX/TX-State
der Bänder selbst.

### Kalibrier-Dateien ✅
Multiband nutzt **dieselben Gain- und Tune-Dateien wie der Normal-
Modus** — kein separater Multiband-Store. Gain und Tune sind praktisch
dasselbe wie im Normal-Betrieb (beide per Band gespeichert, der Unified
Gain Store ist ohnehin modus-übergreifend).

---

## DeepSeek-Review (V4-pro, 2026-05-22)

**Urteil:** Konzept durchdacht, physikalisch korrekt, gut für ein
Hobby-Tool geeignet — **Umsetzung empfohlen**. Kein Overengineering.

**Korrektur eines DeepSeek-Irrtums:** DeepSeek nannte als Hauptrisiko die
parallele Dekodierung („WSJT-X-Fortran-Bibliothek nicht re-entrant").
Das trifft nicht zu — SimpleFT8 nutzt **`ft8_lib` (C, kgoba)**, nicht den
WSJT-X-Decoder. Beide Bänder werden nacheinander dekodiert, kein
Parallelitäts-Problem. Auch der Zeitsync-Einwand ist erledigt
(`core/ntp_time.py` existiert bereits).

**Valide Findings — bei der Umsetzung Pflicht:**
1. **Restzeit deterministisch** — Fall A: statt vagem „~3 s" ein fester
   Cutoff (z.B. „ab ~12 s nach Slot-Start zu spät → nächsten Slot").
   Pro Modus skaliert (FT8 15 s, FT4 7,5 s → andere Grenze).
2. **Kein TX vor gültigem TUNE** — in F5 eingearbeitet (Hardware-
   Sicherheit).
3. **Gain-Default sichtbar machen** — läuft ein Band auf dem ~10-dB-
   Default (nie gemessen), dezenter UI-Hinweis.
4. **Slice-Cleanup** — der 2. Slice muss bei Multiband-Ende und auch bei
   App-Absturz sauber freigegeben werden, sonst bleibt er belegt.
5. **Modus-Übergang Normal→Multiband** — Mechanik beschreiben: 2. Slice
   allokieren, DAX-Kanal zuweisen, 2. RX-Stream starten (nutzt den
   adaptierten Slice-B-Code).

---

## Auto-Hunt bei zwei Bändern — Architektur & DeepSeek-Härtung (2026-06-03)

**Anlass (Mike):** „Wie bekommen wir Auto-Hunt bei 2 erfassten Bändern hin?
Das geht ja nur, wenn wir nach der Empfangsliste arbeiten und speichern, auf
welchem Band sich die Station befindet." — exakt richtig erkannt. Mike's zweite
Sorge: „Bauen wir einen kompletten neuen Pfad, oder zerstören wir den
bestehenden, field-validierten Einzelband-Pfad?" Diese Frage wurde mit DeepSeek
(V4-pro) ein zweites Mal durchgesprochen.

### Grundsatz-Entscheidung: dünne additive Schicht, Kern unangetastet (Modell 3)

Drei denkbare Wege:
- **Modell 1 — kompletter Parallel-Pfad** (Multiband fährt alles selbst, Normal
  bleibt 100% unberührt): **verworfen.** Müsste den gefährlichsten Code
  (QSO-State-Machine, Encoder, Slot-Timing) duplizieren → doppelte Pflege,
  Drift-Risiko, Overengineering — und greift am Ende doch auf dieselbe eine PA.
- **Modell 2 — Kern umschreiben** (Band überall zur Variablen): maximal KISS,
  aber Eingriff mitten ins funktionierende Herz. **Verworfen** (Mikes Angst).
- **Modell 3 — dünne Schicht obendrauf:** **gewählt.** Die Grenze liegt NICHT
  zwischen „Normal" und „Multiband", sondern zwischen zwei Schichten:
  - **Empfang + Bandauswahl** (neu, additiv): 2. Slice füttert dieselbe
    Empfangsliste; jede Station trägt ein Band-Etikett; vor dem Anruf wird
    einmal „stimm TX-Band auf X" eingeschoben.
  - **QSO + Senden + Timing + Hardware** (unverändert, geteilt): sobald gerufen
    wird, läuft EXAKT der heutige Pfad — er weiß nichts von Multiband. Da es nur
    einen Sender + ein QSO zur Zeit gibt, braucht es hier KEINEN zweiten Pfad.

**DeepSeek-Urteil (2. Runde):** Modell 3 ist der KISS-este UND sicherste Weg.
Größte Gefahr ist keine Fehlkonstruktion, sondern die **Unterschätzung der
Band-Umschalt-Schicht** (s.u.) — die muss hart getestet werden.

**Drei Sicherungen gegen das „Kern-kaputt-machen"-Risiko:**
1. **Band als Parameter mit Default = aktuelles Band** → im Einzelband-Betrieb
   ist „das Band der Station" immer das eine aktive Band → Verhalten
   **bit-identisch** wie heute.
2. **Die Bestands-Tests bleiben grün** = mathematischer Beweis, dass
   Normal/Diversity unverändert sind.
3. **Feature-Flag:** Multiband aus → 2. Slice nie allokiert, Band-Schicht
   inaktiv, heutiger Code läuft.

### Auto-Hunt konkret band-aware machen

- **Band-Etikett ab Decode:** Jede dekodierte Nachricht trägt ihr Quell-Band
  (welcher Slice). Der Aggregator vergibt **IMMER** ein Band, **nie `None`** —
  im Einzelband-Modus schlicht das aktuelle Band. (DeepSeek-Bedingung für
  Bit-Identität.)
- **`_HuntCandidate` kriegt additiv ein `band`-Feld** (Default = `self._band`).
- **In `select_next` ALLE `self._band` → `c.band`** an diesen Stellen:
  1. Worked-Filter `is_worked_on_band_mode(c.call, c.band, self._mode)`.
  2. Recent-QSO-Cooldown-Key `(base, c.band.upper(), self._mode.upper())`.
  3. **Fail-Cooldown-Key** `_cooldown` → von reinem `call` auf `(call, band)`
     erweitern (🟡 DeepSeek: sonst sperrt ein Fehlversuch auf 15m denselben
     Call auf 20m). Kleine, risikofreie Änderung.
  4. DX-Scoring `_compute_priority` „Land auf diesem Band neu?" über `c.band`.
  Im Einzelband ist `c.band == self._band` → identisches Verhalten.
- **Kandidaten-Pool aus beiden Bändern** gespeist (jede msg mit Band-Tag) →
  Auto-Hunt vergleicht DX-Wert bandübergreifend.

### 🔴 PFLICHT: interner TX-Bandsprung ≠ User-Bandwechsel (DeepSeek-Blocker)

Heute: manueller Bandwechsel → `on_band_change` → `stop_auto_hunt("band_change")`
= **bewusster, harter Auto-Hunt-Stop** (Session-Ende). Im Multiband muss der
**automatische** Bandsprung beim Pick die Auto-Hunt-Session aber **behalten** —
sonst beendet Auto-Hunt sich beim ersten Bandsprung selbst (funktionaler
Fehler).

**Lösung (Pflicht bei Umsetzung):** zwei getrennte Wege —
- **`switch_tx_band(band)` (intern, NEU):** stellt `_band` + Radio aufs Zielband
  um, resettet `_last_tx_even` (Slot-Parität) und `_all_worked_reported`, lässt
  `active` **unberührt** → KEIN `stop_auto_hunt`. Für den Pick-getriebenen
  Bandsprung binnen einer Session.
- **`set_band(band)` (extern, User-Klick):** bleibt wie heute = harter
  Session-Stop. Der bewusste User-Bandwechsel beendet Auto-Hunt weiterhin sofort.

### 🟠 Die Band-Umschalt-Sequenz ist ein eigener, sensibler Baustein

Vor dem ersten TX aufs Zielband: TX-Flag auf den Ziel-Slice, 6h-Cache-Werte
(Power/Gain) setzen, ATU-Lösung recallen, ggf. Tune-Slot einplanen (Fall A/B
oben). Das ist **zeitkritische neue Logik auf Encoder-Höhe**, kein trivialer
Additiv-Layer — sie muss in den Slot-Zyklus (`mw_cycle`) eingepasst werden
(Restzeit-Prüfung, Slot-Parität erhalten). Wo möglich die **bestehenden
manuellen-Bandwechsel-Methoden wiederverwenden** statt neu bauen. Evtl. ein
`prepare_tx_band(band)` am Radio/Encoder-Interface.
**ANT1 IMMER** — vor jedem TX `set_tx_antenna("ANT1")` verifizieren (Hardware).
→ **Isoliert entwerfen + eigene Tests**, nicht „nebenbei".

### Bandsprung-Politik: natürliche Hysterese statt expliziter Schwelle

**Ziel (Mike, „Modell B"):** am aktuellen Band kleben, nicht ständig hüpfen
(jeder Sprung kostet das andere Band kurz Empfang — ein Sender, TX blockt RX).

**Erkenntnis (DeepSeek):** Das lexikografische DX-Scoring (Seltenheit >>
Land-auf-Band-neu >> Distanz >> SNR >> Slot) **liefert diese Hysterese schon von
selbst** — ein Bandsprung passiert nur, wenn die beste Station des anderen
Bandes in der Seltenheits-Rangordnung vorne liegt; ein bloß lauteres Signal
derselben Seltenheitsklasse springt NICHT.

**Entscheidung (Claude, Boss):** **Erster Release OHNE explizite
Hysterese-Schwelle** (KISS — natürliche Scoring-Hysterese nutzen). Im Feld
beobachten. **Nachrüst-Pfad nur falls Mike zu häufiges Bandhüpfen meldet:**
erzwungener Verbleib am aktuellen TX-Band, außer die andere-Band-Station ist
um **≥2 Seltenheitsklassen** besser (ATNO/extrem-selten vs. Allerweltsland).
So bleibt Mikes Wunsch (B) gewahrt, ohne Komplexität auf Verdacht.

### Manueller Station-Klick bei laufendem Auto-Hunt (Multiband)

Konsistent zum Einzelband: Ein **manueller Klick/Doppelklick auf eine Station**
ist eine bewusste Übernahme → **harter Auto-Hunt-Stop** (wie P166 im Einzelband,
kein Auto-Resume). Sitzt die geklickte Station auf dem anderen Band, wird das
TX-Band dabei auf ihr Band gestellt — der nötige Bandwechsel läuft hier über den
**Anruf-Pfad** (die Auto-Hunt-Session endet ohnehin), NICHT über das
session-erhaltende `switch_tx_band`. Das „laufendes QSO → Klick puffern,
CQ/unbeantworteter Anruf → sofort wechseln"-Verhalten (Abschnitt „QSO-Verhalten
beim Band-Klick") bleibt unverändert gültig.

### 🟡 Weitere Detail-Anpassungen (DeepSeek)

- **`all_worked`-Signal Multiband-tauglich — Entscheidung: pro Band auswerten.**
  Heute ein globales Flag + Signal mit EINEM Band. Im Multiband wird der
  „alle CQ-Stationen schon gearbeitet"-Zustand **pro Band** ermittelt und die
  Meldung nennt das jeweilige Band („Auto-Hunt: alle N Stationen auf {Band}
  {Mode} schon gearbeitet"). Kein globales Flag über beide Bänder (das wäre
  verwirrend, wenn ein Band voll, das andere offen ist).
- **`_last_tx_even` Slot-Tiebreaker** wird band-übergreifend — **kein**
  Fehlverhalten, nur ein beobachtbarer Unterschied zum reinen Einzelband.
  Unkritisch.

### Umsetzungs-Reihenfolge (DeepSeek-Empfehlung, übernommen)

1. **Zuerst** den internen Band-Wechsel-Mechanismus (`switch_tx_band`) bauen +
   **isoliert testen** — die gefährliche Zone zuerst im Griff haben.
2. **Dann** die Decode-Aggregation (2. Strom annehmen) + band-getaggten
   Kandidaten-Pool.
3. **Dann** Scoring/Filter/Cooldowns auf `c.band` umstellen + Detail-Punkte.
4. Bei der tatsächlichen Umsetzung: **eigener voller Workflow-Zyklus**
   (V1→V2→R1→V3) — die 🔴/🟠-Punkte oben als Pflicht.

---

## Nächster Schritt

Konzept vollständig und **zweifach** DeepSeek-geprüft (Urteil: Umsetzung
empfohlen, Modell 3 = dünne Schicht). Offen ist nur noch die
**Umsetzungs-Entscheidung** — ob/wann Multiband gebaut wird. Bei Umsetzung:
eigener voller Workflow-Zyklus, die fünf Review-Findings (DeepSeek 22.05.) **und**
die Auto-Hunt-Findings (🔴 interner vs. externer Bandwechsel, 🟠 Band-Umschalt-
Sequenz isoliert testen, 🟡 Fail-Cooldown `(call,band)` + `all_worked`) als
Pflicht-Punkte, in der Reihenfolge oben.
