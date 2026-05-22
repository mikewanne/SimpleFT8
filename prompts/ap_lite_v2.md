# V2 — AP-Lite (P2-Lite): Diagnose verifizieren + Strategie empfehlen

Du bist Senior-Entwickler für Amateurfunk-DSP und FT8-Signalverarbeitung
(NumPy, ft8_lib, PySide6). Das Projekt „SimpleFT8" ist ein Hobby-Funker-Tool
für einen einzelnen Operator — kein Contest-Tool, KISS-Prinzip, Over-
engineering gilt selbst als Fehler.

**Deine Aufgabe — zwei Teile:**
1. **Diagnose verifizieren:** Prüfe die unten stehende Fehleranalyse gegen
   den angehängten Code. Bestätige oder widerlege jeden Punkt konkret.
2. **Strategie empfehlen:** Gib eine begründete, unabhängige Empfehlung,
   was mit AP-Lite geschehen soll (reparieren / neu konzipieren /
   deaktivieren). Du darfst meine Optionen verwerfen und eigene vorschlagen.

Antworte strukturiert. Bei Findings: Tabelle Schwere | Punkt | Datei:Zeile |
Bewertung. Kennzeichne Halluzinations-Risiken in meiner Analyse offen.

---

## Kontext: Was AP-Lite sein soll

Wenn der FT8-Decoder das Signal des QSO-Partners nicht schafft und die
Gegenstation (FT8-Standard) ihre Nachricht wiederholt, soll AP-Lite zwei
fehlgeschlagene PCM-Slots „kohärent addieren" → laut interner Doku ~4-5 dB
SNR-Gewinn → marginales QSO doch noch gerettet. Kandidaten-Nachrichten
werden aus dem QSO-Zustand erzeugt (WAIT_REPORT → Report-Strings,
WAIT_RR73 → RR73/RRR/73) und gegen den kombinierten Buffer korreliert;
Score ≥ `SCORE_THRESHOLD = 0.75` → angenommen.

## Verifizierter Ist-Zustand

- `core/ap_lite.py`: `AP_LITE_ENABLED = True` (Z.35). Läuft jeden Zyklus
  via `ui/mw_cycle.py:_run_ap_lite_rescue` (Z.450, aufgerufen Z.133).
- Erfolgsfall: nur `qso_panel.add_info(...)`, **kein TX** — reiner
  RX-/Anzeige-Pfad.
- `main_window.py:395` Kommentar UND `docs/explained/ap-lite_de.md` Status
  behaupten „AP_LITE_ENABLED=False / deaktiviert" — beide sind faktisch
  falsch, das Flag ist True.
- 39 Tests. Das E2E-Assert „Score > 0" wurde in v0.95.10 entfernt, weil es
  nie erfüllt war (`test_try_rescue_state1_runs_after_fix` dokumentiert das).
- AP-Lite hat seit Implementierung (v0.22 Skeleton, v0.26 voll) **kein
  einziges QSO gerettet**.

## Eigene Messungen (synthetisches FT8, `Encoder.generate_reference_wave`)

1. `align_buffers(clean, clean.copy())` mit zwei IDENTISCHEN sauberen
   Buffern → liefert `dt=-6 Samples, df=-1.5 Hz` statt dt=0/df=0.
   df rallt exakt an den Suchbereichsrand (`ALIGN_DF_HZ=1.5`).
2. `try_rescue` mit zwei identischen sauberen Buffern (State 2, RR73):
   **Score 0.42**, `success=False` (Schwelle 0.75). Der perfekte Fall scheitert.
3. `try_rescue` mit zwei −8 dB-verrauschten Buffern: Score 0.16.
4. Phasen-Test (Trägerphase φ des 2. Slots künstlich gedreht, dann addiert):

   | φ | P_combined / P_single | Netto-Gewinn über Mittelung |
   |---|---|---|
   | 0° | 4.0× | +3.0 dB |
   | 90° | 2.0× | 0.0 dB |
   | 180° | 0.0× | totale Auslöschung |
   | Mittel über alle φ | 2.0× | 0.0 dB |

## Meine Diagnose — drei Fehler, zwei Ebenen

### Ebene A (flach, einzelne Funktion)

**A1 — `_build_costas_reference` (ap_lite.py:156) ist eine Sinus-Näherung.**
Erzeugt die Referenz aus unabhängigen `np.sin()`-Stücken pro Costas-Symbol,
kein echtes FT8-GFSK mit kontinuierlichem Phasenverlauf (eigener Code-TODO).
→ `align_buffers` findet ein falsches Korrelationsmaximum → spurious dt/df.

**A2 — `align_buffers` Frequenzkorrektur ist DSP-naiv (ap_lite.py:214,231).**
`corrected = shifted * np.cos(2*pi*df*t)` — Multiplikation eines REALEN
Bandpass-Signals mit einem reellen Cosinus erzeugt Summen- UND
Differenzfrequenzen (Spiegel um jede Komponente), keine saubere
Einseitenband-Verschiebung. Eine echte Frequenzkorrektur bräuchte das
analytische Signal (Hilbert) und komplexe Multiplikation. → der „korrigierte"
Buffer ist verzerrt, selbst wenn df stimmen würde.

Folge A1+A2: selbst zwei identische Buffer werden verrollt + verzerrt →
`correlate_candidate` scort 0.42 statt hoch.

### Ebene B (tief, konzeptionell)

**B1 — kohärente Addition über 15-s-Slots ist phasenabhängig.**
Die Doku-Rechnung `x1+x2 = 2s+(n1+n2)` → +3 dB netto gilt NUR bei
Trägerphasen-Kohärenz. Zwei reale FT8-Sendungen ~15 s auseinander haben
zufällige relative Trägerphase. `align_buffers` sucht Zeit- + Frequenz-
Offset, aber **nicht** die Trägerphase (Code-TODO sagt das). Messung 4
zeigt: Mittel über zufällige φ = 0 dB Netto-Gewinn. Die versprochenen
+4-5 dB existieren nur bei φ≈0.

**B2 — Test-Trugschluss.** Die E2E-Pipeline erzeugt `pcm1`/`pcm2` aus
identischen `generate_reference_wave`-Aufrufen → phasengleich. Sie testet
B1 nie. Ein reiner A-Fix würde die E2E-Tests grün machen, das Feld-Verhalten
bliebe ~0 dB.

## Strategie-Optionen (du darfst eigene ergänzen)

- **A — Nur Ebene A fixen.** Echte Costas-GFSK-Referenz + saubere
  komplexe Frequenzkorrektur. E2E-Tests grün, identische Buffer scoren hoch.
  Ebene B bleibt → im echten Betrieb weiter ~0 dB. Grüner Test, totes Feature.
- **B — Ehrlich deaktivieren.** `AP_LITE_ENABLED=False`, Falsch-Kommentar +
  Doku berichtigen, README-Feature als „experimentell/inaktiv". KISS-ehrlich.
- **C — Neu: Soft-Symbol-/LLR-Mittelung** (WSJT-X-„message averaging"-
  Prinzip): Slots demodulieren, Soft-Decision-Symbolmetriken (LLRs) der
  Empfänge mitteln, dann LDPC/Costas-Decoder darauf. Phasen-robust, aber
  großer, tiefer Eingriff (Tage).

## Randbedingungen

- Hobby-Tool, KISS. Overengineering ist selbst ein Fehler.
- Mike ist ~4 Wochen vom Radio entfernt → keine Feld-Kalibrierung des
  Thresholds möglich.
- AP-Lite = produktiver Algorithmus → Strategie-Entscheidung braucht
  Operator-Freigabe vor Code.
- Reiner RX-/Anzeige-Pfad, kein TX.

## Fragen an dich

1. **Diagnose:** Stimmen A1, A2, B1, B2? Insbesondere — ist meine
   Phasen-Analyse (B1) für FT8-GFSK korrekt, oder gibt es eine FT8-
   spezifische Feinheit, die ich übersehe? Ist A2 (real×cos erzeugt
   Spiegel) tatsächlich ein Bug oder in diesem Kontext harmlos?
2. **Tragfähigkeit:** Ist die rohe-PCM-kohärente-Addition über 15-s-Slots
   konzeptionell rettbar, oder tot?
3. **Mittelweg:** Gibt es einen pragmatischen Phasenausgleich (z.B.
   komplexe Demodulation + globale/per-Symbol-Phasenschätzung), der ohne
   vollen LDPC-Soft-Decision-Decoder echten Gewinn bringt und für ein
   Hobby-Tool vertretbar ist?
4. **Ansatzfrage:** Wäre es sinnvoller, statt des Eigenbau-`correlate_
   candidate` den echten ft8_lib-Decoder auf den kombinierten Buffer
   loszulassen? Oder scheitert das genauso an Ebene B?
5. **KISS-Empfehlung:** Wenn nur C echten Nutzen brächte — lohnt sich das
   für ein Hobby-Tool, oder ist B die richtige Antwort? Falls B: AP-Lite
   nur deaktivieren oder ganz aus dem Code entfernen?
6. Übersehe ich eine einfachere Lösung?

## Akzeptanzkriterien des Ergebnisses

- Begründete Strategie-Empfehlung (A/B/C oder Variante).
- Falls Code folgt: was genau, mit Test-Schutz, ohne Radio prüfbar.
- Falsch-Kommentar (`main_window.py:395`) + Doku-Lüge (`ap-lite_de.md`)
  werden in jedem Fall berichtigt.
- Falls Ebene A/C angefasst wird: E2E-Test mit phasenverschobenem zweitem
  Slot ist Pflicht (sonst testet die Pipeline weiter am kritischen Pfad
  vorbei — Projekt-Memory `feedback_test_critical_path_not_mock.md`).
