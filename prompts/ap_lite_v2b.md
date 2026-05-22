# V2b — AP-Lite: KORRIGIERTES Konzept (A-Priori) — Review

Du bist Senior-Entwickler für Amateurfunk-DSP und FT8-Signalverarbeitung
(NumPy, ft8_lib, PySide6). „SimpleFT8" ist ein Hobby-Funker-Tool für einen
einzelnen Operator. KISS-Prinzip, Overengineering gilt selbst als Fehler.

**Wichtig — Prämissen-Korrektur gegenüber einem früheren Review:** Ein
erstes Review bewertete AP-Lite als „kohärente Addition zweier Slots für
SNR-Gewinn" und empfahl, das Feature zu deaktivieren. Der Operator hat
klargestellt: **das war nie das Konzept.** „AP" = *a priori*. Es geht NICHT
ums Signal-Entschlüsseln oder SNR-Stapeln. Es geht darum, dass wir während
eines QSOs fast die ganze Nachricht KENNEN (beide Rufzeichen, Nachrichten-
Struktur aus dem QSO-Zustand) und nur die wenigen Restvarianten brute-force
gegen den Empfang matchen.

**Deine Aufgabe:** Den unten stehenden korrigierten Plan prüfen — ist der
A-Priori-Ansatz statistisch tragfähig, sind die drei Fixes korrekt und
KISS-angemessen? Findings als Tabelle Schwere | Punkt | Bewertung.

---

## Konzept (korrigiert)

Wenn der FT8-Decoder das Signal des QSO-Partners nicht schafft: Wir kennen
aus dem QSO-Zustand die wenigen möglichen Nachrichten (WAIT_RR73 → genau 3:
`RR73`/`RRR`/`73`; WAIT_REPORT → ~6-16 Report-Werte). Wir erzeugen für
jeden Kandidaten das FT8-Referenzsignal und matchen es gegen den EINEN
empfangenen (fehlgeschlagenen) Slot. Gewinnt ein Kandidat klar → angenommen.
Kein zweiter Slot, keine Addition, kein SNR-Gewinn-Anspruch.

## Ist-Zustand des Codes (verifiziert)

`core/ap_lite.py` ist ein Hybrid: der A-Priori-Teil ist da
(`generate_candidates` — korrektes Konzept), aber daraufgesetzt auf einen
**kohärente-Addition-Mechanismus** (`align_buffers`, `_build_costas_
reference`, Zwei-Slot-Buffering) — das ist die konzeptionelle Abdrift.
`AP_LITE_ENABLED=True`, läuft jeden Zyklus, hat aber **nie ein QSO
gerettet**.

## Messungen (synthetisches FT8, `Encoder.generate_reference_wave`)

**M1 — A-Priori-Matching rankt korrekt, tief runter:** richtiger Kandidat
(RR73) gegen einen Slot, 8 Rausch-Realisierungen pro SNR:

| SNR | Score richtig | Score falsch | richtig vorn |
|---|---|---|---|
| 0 dB | 0.72 | 0.26 | 8/8 |
| −10 dB | 0.31 | 0.11 | 8/8 |
| −16 dB | 0.16 | 0.06 | 8/8 |
| −24 dB | 0.067 | 0.021 | 8/8 |

**M2 — warum AP-Lite nie feuerte:** `SCORE_THRESHOLD=0.75` (absolut) ist
unerreichbar — selbst bei 0 dB scort der richtige Kandidat nur 0.72, bei
brauchbarem FT8-SNR (−10..−20 dB) nur 0.1-0.3. Die absolute Schwelle ist
das falsche Werkzeug. Das *Ranking* ist dagegen perfekt.

**M3 — Fehlalarm sauber trennbar.** Marge = bester − zweitbester Kandidat,
12 Realisierungen:

| Szenario | Marge Mittel | Marge max |
|---|---|---|
| echtes RR73 vorhanden (−15 dB) | +0.114 | +0.123 |
| nur Rauschen | +0.002 | +0.006 |
| fremde Nachricht ("CQ JA1XYZ") | +0.012 | +0.023 |

→ 10×+ Trennung echt vs. kein-echtes-Signal. Ein **relativer Margen-Test**
ist statistisch tragfähig.

**M4 — Phasen-Bug + Fix verifiziert.** `correlate_candidate` nutzt ein
reelles Skalarprodukt → phasen-kohärent: gleiches Signal, Trägerphase
gedreht → Score 1.0 (0°) / 0.0 (90°) / 0.0 (180°). Ein nicht-kohärenter
Prototyp (analytisches Signal via Hilbert, Betrag der komplexen
Korrelation) ist messbar **phasen-invariant**: 0°/45°/90°/135°/180° alle
Score 1.0.

## Vorgeschlagener Plan (Option D — A-Priori zurückbauen)

1. **Stapel-Mechanik löschen:** `align_buffers`, `_build_costas_reference`,
   Zwei-Slot-Buffering (`on_decode_failed` Puffer, `try_rescue` Addition).
   AP-Lite arbeitet auf EINEM fehlgeschlagenen Slot. → Code schrumpft.
2. **`correlate_candidate` nicht-kohärent machen:** analytisches Signal
   (Hilbert) + Betrag der komplexen Kreuzkorrelation. Verifiziert
   phasen-invariant (M4).
3. **Detektion = relativer Margen-Test** statt absoluter Schwelle: bester
   Kandidat muss den zweitbesten um ≥ MARGIN_MIN schlagen. M3 legt
   MARGIN_MIN ≈ 0.05 nahe (deutlich über Rausch-/Fremd-Ceiling 0.012,
   deutlich unter Echtsignal-Marge 0.11).
4. **`generate_candidates` bleibt** (korrektes Konzept). Costas-gewichtete
   Korrelation in `correlate_candidate` kann bleiben oder vereinfacht
   werden — du bewertest.

## Fragen an dich

1. **Margen-Test statistisch sauber?** Bei 3 Kandidaten und MARGIN_MIN≈0.05:
   ist die Falsch-Positiv-Rate für QSO-Logging vertretbar? Sollte der Test
   zusätzlich eine absolute Mindest-Korrelation verlangen (Hybrid:
   Marge UND Score > klein)?
2. **Frequenz-Offset:** Der Partner kann ±einige Hz neben der erwarteten
   Frequenz liegen. Sollte der nicht-kohärente Korrelator zusätzlich ein
   kleines Frequenz-Fenster absuchen (z.B. ±5 Hz) und das Maximum nehmen?
3. **„Teilfehler ersetzen":** Der Operator erwähnt, bei TEILWEISE
   gelungenem Decode die fehlerhaften Teile a priori zu ersetzen. Bietet
   ft8_lib Zugriff auf partielle/Soft-Decode-Information, die das stützen
   würde — oder ist reines Kandidaten-Matching gegen den Slot der ganze
   sinnvolle Hebel?
4. **Stapel-Mechanik wirklich ganz löschen** — oder gibt es einen Grund,
   eine Zwei-Slot-Option zu behalten?
5. KISS-Check: ist Option D der richtige Umfang für ein Hobby-Tool, oder
   übersiehst du eine einfachere/sauberere Variante?

## Randbedingungen

- Hobby-Tool, KISS. Reiner RX-/Anzeige-Pfad, kein TX.
- Operator ist ~4 Wochen vom Radio entfernt → MARGIN_MIN final feld-zu-
  kalibrieren, aber synthetisch ist ein solider Startwert ableitbar.
- AP-Lite = produktiver Algorithmus → finale Strategie braucht Operator-OK.

## Akzeptanzkriterien

- Begründetes Urteil: ist Option D tragfähig? Falls ja, mit welchen
  Korrekturen am Plan.
- E2E-Test-Pflicht: Tests müssen mit PHASEN-VERSCHOBENEM und
  frequenz-versetztem Signal arbeiten (nicht nur identische Buffer) —
  sonst testet die Pipeline am kritischen Pfad vorbei.
- Falsch-Doku (`main_window.py:395`-Kommentar, `docs/explained/
  ap-lite_de.md`, README) wird in jedem Fall berichtigt.
