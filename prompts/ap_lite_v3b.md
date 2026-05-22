# V3b — AP-Lite: FINAL — A-Priori zurückbauen (Option D)

**Ersetzt `ap_lite_v3.md`** (das empfahl „deaktivieren" — basierte auf der
falschen Prämisse „kohärente Addition". Mike hat klargestellt: AP = a priori,
Kandidaten-Matching, kein Slot-Stapeln.)

**Status: wartet auf Mike-Freigabe. Kein Code vor explizitem OK.**

## Empfehlung: Option D — AP-Lite auf das ursprüngliche A-Priori-Konzept zurückbauen

Einstimmig: Mikes Konzept-Korrektur, eigene Messungen, DeepSeek-Review
(Runde 2). Das Feature ist **rettbar** — der Code hatte nur den falschen
Mechanismus drangeschraubt.

## In einfachen Worten

AP-Lite soll keine Signale entschlüsseln und kein SNR „stapeln". Es soll das
tun, was es laut Name immer sollte (AP = a priori): Während eines QSOs
kennen wir fast die ganze Nachricht — beide Rufzeichen, die Struktur. Es
bleiben nur wenige Restvarianten (bei „warte auf RR73" genau drei: RR73,
RRR, 73). Wenn der Decoder den Partner nicht schafft, probieren wir diese
wenigen Varianten gegen den Empfang durch und nehmen die, die klar passt.

Das funktioniert — gemessen, ohne Radio:
- Der richtige Kandidat gewinnt das Rennen zuverlässig bis −24 dB SNR.
- Echte Nachricht vs. Rauschen ist um Faktor 10+ trennbar.
- Warum es bisher nie ging: eine absolute Schwelle (0,75), die kein reales
  Signal je erreicht, und eine phasen-empfindliche Korrelation.

## Was geändert wird (3 Fixes + Aufräumen)

1. **Stapel-Mechanik restlos löschen.** `align_buffers`,
   `_build_costas_reference`, `FailedDecodeBuffer`, das `_buffers`-Cache,
   `on_decode_failed` und die Zwei-Slot-Addition in `try_rescue`. AP-Lite
   arbeitet auf **einem** fehlgeschlagenen Slot, ohne Vorgeschichte.
   → Modul wird deutlich kleiner.

2. **`correlate_candidate` nicht-kohärent machen.** Analytisches Signal
   (Hilbert) + Betrag der komplexen Kreuzkorrelation → phasen-invariant
   (M4 verifiziert: 0°/90°/180° alle Score 1.0 statt 1.0/0.0/0.0).
   **Plus Frequenz-Offset-Scan** (DeepSeek-Ergänzung): intern ±5 Hz in
   1-Hz-Schritten absuchen, Maximum nehmen — reale Stationen liegen
   ±2-5 Hz neben der Sollfrequenz.

3. **Detektion = relativer Margen-Test.** `SCORE_THRESHOLD=0.75` (absolut)
   raus. Neu: bester Kandidat muss zweitbesten um ≥ `MARGIN_MIN` schlagen.
   Startwert `MARGIN_MIN = 0.05` (M3: Rausch-/Fremd-Ceiling 0.023,
   Echtsignal-Marge 0.11 — sicher dazwischen). Optionaler kleiner
   absoluter Mindest-Score (~0.03) als Gürtel-und-Hosenträger; laut
   DeepSeek nicht zwingend.

4. **`generate_candidates` bleibt** unverändert (war immer das korrekte
   A-Priori-Konzept). Die Costas-Gewichtung in der Korrelation kann
   entfallen — bei nicht-kohärenter Vollsignal-Korrelation unnötig.

## API-/Verdrahtungs-Folge

- `try_rescue` bekommt eine neue Signatur: ein Slot rein, sofort
  Kandidaten-Match, `APLiteResult` raus. Kein `on_decode_failed`,
  kein Zwei-Aufruf-Tanz.
- `ui/mw_cycle.py:_run_ap_lite_rescue` (Z.450) wird entsprechend
  vereinfacht: bei QSO-Partner-Decode-Fail EINMALIG Kandidaten-Match auf
  dem aktuellen Slot, statt erst puffern / nächsten Slot abwarten.
- `mw_qso.py:422` `clear()` und der Statusbar-Zähler bleiben.

## Tests

- `tests/test_ap_lite_e2e.py` + `test_ap_lite.py` neu aufsetzen: Signale
  mit **Trägerphasen-Drehung** (0/90/180°) UND **Frequenz-Offset** (z.B.
  3 Hz) — sonst testet die Pipeline wieder am kritischen Pfad vorbei
  (Memory `feedback_test_critical_path_not_mock.md`). Tests für
  align_buffers/Stapeln fallen weg.
- Neue Tests: Margen-Test (echt vs. Rauschen vs. fremd), Frequenz-Scan,
  Phasen-Invarianz.

## Doku (in jedem Fall)

- `core/ap_lite.py` Modul-Docstring: A-Priori-Konzept statt „kohärente
  Addition".
- `ui/main_window.py:395` Kommentar berichtigen.
- `docs/explained/ap-lite_de.md` + `_en`: komplett auf A-Priori-Konzept
  umschreiben (die „+4-5 dB kohärente Addition"-Story war nie korrekt).
- `README.md`/`README_DE.md`: AP-Lite-Beschreibung anpassen *(GitHub-
  sichtbar → Mike-Wortlaut)*.
- `TODO.md`: veraltete „AP-Lite Test-Pipeline bauen"-Sektion schließen.

## Offene Frage für Mike (vor TX/Logging-Scharfschaltung)

Ein erfolgreicher Match „rettet" ein QSO → es wird geloggt. Falsch-Positiv
= geloggtes QSO das nie stattfand. Die synthetische Messung ist beruhigend
(saubere 10×-Trennung), aber `MARGIN_MIN` sollte im Feld fein-kalibriert
werden. Vorschlag: Option D umsetzen, `AP_LITE_ENABLED` aber erst nach
deinem Feld-Check auf True — oder konservativ mit `MARGIN_MIN` hoch
(z.B. 0.08) starten. Deine Entscheidung.

## „Teilfehler ersetzen"

Du hattest erwähnt, bei teilweise gelungenem Decode die fehlerhaften Teile
a priori zu ersetzen. DeepSeek-Befund: ft8_lib gibt keine partiellen
Soft-Decode-Daten heraus (LLR pro Symbol) — daran käme man nur mit tiefem
Bibliotheks-Eingriff. Das volle Kandidaten-Matching gegen den Slot erreicht
aber dasselbe Ziel (die ganze erwartete Nachricht zurückgewinnen), ohne
diesen Eingriff. Falls du echte Teil-Symbol-Ersetzung willst, wäre das ein
eigenes, größeres Thema — sag Bescheid.

## Aufwand

Modul-Rewrite `core/ap_lite.py` (wird kleiner) + Verdrahtung `mw_cycle.py`
+ Test-Neuaufsatz + Doku. ~1/2 Tag. Voll ohne Radio test- und prüfbar
(synthetisches FT8). `MARGIN_MIN`-Endwert braucht später einen Feld-Check.

## DeepSeek-Findings (Runde 2) — Bilanz

- Option D + alle 3 Fixes: **bestätigt**, KISS-konform.
- Ergänzung **angenommen**: Frequenz-Offset-Scan ±5 Hz im Korrelator.
- Ergänzung **angenommen**: `FailedDecodeBuffer`-Klasse ganz entfernen.
- Costas-Gewichtung entfernen: **angenommen** (in nicht-kohärenter
  Variante unnötig).
- Optionaler absoluter Mindest-Score: **als Option vermerkt**, nicht
  zwingend — Mike/Feld entscheidet.
- 0 Halluzinationen. Modell: `deepseek-v4-pro` (Helper-Default).

## Nicht gemacht

- Option A (Stapel-Mechanik reparieren) — Stapeln war nie das Konzept.
- Option B (deaktivieren) — war die Empfehlung aus v3, basierte auf
  falscher Prämisse, hinfällig.
- Option C (LLR-Decoder-Umbau) — nicht nötig, Kandidaten-Matching reicht.
