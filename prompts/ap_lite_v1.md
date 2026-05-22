# V1 — AP-Lite (P2-Lite): Diagnose + Strategie

## 1. Ziel

Klären, warum AP-Lite seit Implementierung **nie ein QSO gerettet hat**, und
entscheiden, was wir brauchen: das Feature reparieren, neu konzipieren oder
ehrlich deaktivieren. Eine Sache pro Prompt — hier: Strategie-Entscheidung,
NICHT schon die Implementierung.

## 2. Verifizierter Ist-Zustand (Code gelesen + Messungen gefahren)

**Was AP-Lite sein soll:** Wenn der Decoder ein QSO-Partner-Signal nicht
schafft und die Gegenstation wiederholt, kombiniert AP-Lite zwei
fehlgeschlagene PCM-Slots durch „kohärente Addition" → laut Doku ~4-5 dB
SNR-Gewinn → marginales QSO gerettet.

**Verdrahtung:**
- `core/ap_lite.py` — `AP_LITE_ENABLED = True` (Z.35).
- Läuft jeden Zyklus via `ui/mw_cycle.py:_run_ap_lite_rescue` (Z.450),
  aufgerufen Z.133.
- Bei Erfolg: nur `qso_panel.add_info(...)` — **kein TX-Trigger** (kein
  ANT1/ANT2-Hardware-Risiko, reiner RX-/Anzeige-Pfad).
- Falsch-Doku: `main_window.py:395` Kommentar sagt „AP_LITE_ENABLED=False",
  `docs/explained/ap-lite_de.md` Status sagt „standardmäßig deaktiviert" —
  **beide lügen**, das Flag ist True.
- 39 Tests (`tests/test_ap_lite.py` 24, `tests/test_ap_lite_e2e.py` 15).
  Das E2E-Assert „Score > 0" wurde in v0.95.10 **entfernt**, weil nie erfüllt
  (`test_try_rescue_state1_runs_after_fix` dokumentiert das offen).

**Eigene Messungen (synthetisches FT8 via `Encoder.generate_reference_wave`):**
- `align_buffers(clean, clean.copy())` → meldet `dt=-6 Samples, df=-1.5 Hz`
  bei ZWEI IDENTISCHEN Buffern (korrekt wäre dt=0, df=0). df rallt an den
  Suchbereichsrand (`ALIGN_DF_HZ=1.5`) — klassisches Zeichen einer
  Korrelation ohne echtes Maximum.
- `try_rescue` mit zwei identischen sauberen Buffern (State 2, RR73):
  **Score 0.42**, `success=False` (Schwelle `SCORE_THRESHOLD=0.75`).
  Selbst der perfekte Fall scheitert.
- `try_rescue` mit zwei −8 dB-verrauschten Buffern: Score 0.16.

## 3. Diagnose — zwei Problemebenen

### Ebene A (flach) — `_build_costas_reference` ist eine Sinus-Näherung
`_build_costas_reference` (ap_lite.py:156) erzeugt die Referenz aus
unabhängigen `np.sin()`-Stücken pro Costas-Symbol — kein echtes FT8-GFSK
mit kontinuierlichem Phasenverlauf. Eigener Code-TODO bestätigt das. Folge:
`align_buffers` findet ein falsches Korrelationsmaximum → spurious dt/df →
`combined`-Buffer wird unnötig verrollt und frequenzverschoben →
`correlate_candidate` bekommt eine verschobene Frequenz → Score bricht ein.
Das ist der direkte Grund, warum selbst identische Buffer nur 0.42 scoren.

### Ebene B (tief) — kohärente Addition über 15-s-Slots ist phasenabhängig
Die Doku rechnet `x1+x2 = 2s + (n1+n2)` → +6 dB Signal, +3 dB Rauschen →
+3 dB netto. **Das gilt nur bei Trägerphasen-Kohärenz.** Zwei reale
FT8-Sendungen ~15 s auseinander haben eine zufällige relative Trägerphase
(Sender-Oszillator, Ausbreitungsweg). `align_buffers` sucht Zeit- und
Frequenz-Offset, aber **nicht die Trägerphase** — der Code-TODO in
`align_buffers` sagt das explizit.

Gemessen (Trägerphase φ via Hilbert künstlich gedreht, dann addiert):

| φ | P_combined/P_single | Netto über Mittelung |
|---|---|---|
| 0° | 4.0× | +3.0 dB |
| 90° | 2.0× | 0.0 dB |
| 180° | 0.0× | totale Auslöschung |
| **Mittel über alle φ** | **2.0×** | **0.0 dB** |

→ Bei zufälliger Phase ist der erwartete Gewinn der rohen PCM-Addition
**0 dB**. Die versprochenen +4-5 dB existieren nur bei φ≈0.

### Test-Trugschluss
Die synthetische E2E-Pipeline erzeugt `pcm1` und `pcm2` aus identischen
`generate_reference_wave`-Aufrufen — also phasengleich. Sie testet die
Phaseninkohärenz NIE. Würde man nur Ebene A (Costas-Referenz) fixen, würde
der E2E-Test grün — aber das Feld-Verhalten bliebe ~0 dB. (Projekt-Memory
`feedback_test_critical_path_not_mock.md` — genau dieser Fehlertyp.)

## 4. Strategie-Optionen

- **A — Nur Costas-Referenz fixen.** Echte FT8-Costas-GFSK-Referenz bauen.
  E2E-Tests würden grün, identische Buffer scoren wieder hoch. ABER: Ebene B
  ungelöst → im echten Betrieb weiter ~0 dB Gewinn. Grüner Test, totes
  Feature. **Nicht empfohlen — false confidence.**
- **B — Ehrlich deaktivieren.** `AP_LITE_ENABLED=False`, Falsch-Kommentare
  und Doku berichtigen, Feature in README als „experimentell/inaktiv"
  kennzeichnen. AP-Lite hat noch nie ein QSO gerettet; ein physikalisch
  korrekter Fix ist groß. KISS-ehrlich.
- **C — Neu konzipieren: Soft-Symbol-/LLR-Mittelung.** Der physikalisch
  korrekte Weg (das, was WSJT-X als „message averaging" macht): nicht rohe
  PCM addieren, sondern die Slots demodulieren, die Soft-Decision-Symbol-
  Metriken (Log-Likelihood-Ratios) der beiden Empfänge mitteln, dann den
  LDPC/Costas-Decoder darauf laufen lassen. Phasen-robust, weil im
  Metrik-Raum gemittelt wird. Aber: großes Projekt (Tage), tiefer Eingriff.

## 5. Randbedingungen

- **Hobby-Funker-Tool, KISS.** Overengineering ist selbst ein Fehler
  (CLAUDE.md Projekt-Philosophie + Leitsätze).
- Mike ist ~4 Wochen vom FlexRadio entfernt → Feld-Kalibrierung des
  `SCORE_THRESHOLD=0.75` ist derzeit unmöglich.
- AP-Lite ist ein „produktiver Algorithmus" → Strategie-Entscheidung
  (fix/disable/rewrite) braucht Mike-Freigabe vor Code (CLAUDE.md
  „Architektur-Entscheidungen").
- Reiner RX-/Anzeige-Pfad, kein TX → keine ANT1/ANT2-Pflicht betroffen.

## 6. Nicht im Scope

- Feld-Kalibrierung des Thresholds (Radio nötig).
- Voller LDPC-Soft-Decision-Decoder-Umbau, außer DeepSeek begründet, dass C
  der einzige sinnvolle Weg ist.
- Performance-Optimierung (AP-Lite läuft selten, nur bei QSO-Decode-Fail).

## 7. Fragen an DeepSeek

1. **Verifikation der Diagnose:** Stimmt die Root-Cause-Kette
   `_build_costas_reference`-Vereinfachung → spurious dt/df → Score-Einbruch?
   Und ist die Phasen-Analyse (Ebene B, 0 dB Mittel) physikalisch korrekt?
2. **Tragfähigkeit:** Ist die rohe-PCM-kohärente-Addition über 15-s-Slots
   überhaupt sinnvoll rettbar — oder ist sie konzeptionell tot?
3. **Mittelweg machbar?** Gibt es einen pragmatischen Phasenausgleich
   (z.B. komplexe Demodulation + globale oder per-Symbol-Phasenschätzung),
   der OHNE vollen LDPC-Soft-Decision-Decoder einen echten Gewinn bringt —
   und für ein Hobby-Tool vertretbar ist?
4. **KISS-Empfehlung:** Wenn nur C echten Nutzen brächte — lohnt sich das
   für ein Hobby-Tool, oder ist B (ehrlich deaktivieren + Doku berichtigen)
   die richtige Antwort? Begründung erwünscht.
5. Übersehe ich etwas — z.B. eine viel einfachere Lösung, oder einen
   Grund, AP-Lite ganz aus dem Code zu entfernen statt nur zu deaktivieren?

## 8. Akzeptanzkriterien des Workflow-Ergebnisses

- Klare, begründete Strategie-Empfehlung (A/B/C oder Variante).
- Falls Code folgt: was genau, mit Test-Schutz, ohne Radio prüfbar.
- Falsch-Kommentar (`main_window.py:395`) + Doku-Lüge (`ap-lite_de.md`)
  werden in jedem Fall berichtigt — unabhängig von der Strategie.

## 9. Testbarkeit

- Vorhandene 39 Tests müssen grün bleiben (bzw. bewusst angepasst werden,
  wenn Verhalten absichtlich geändert wird).
- Falls Ebene A/C angefasst wird: ein E2E-Test mit **phasenverschobenem**
  zweitem Slot ist Pflicht — sonst testet die Pipeline weiter am
  kritischen Pfad vorbei.
