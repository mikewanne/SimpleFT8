Final-Code-Review P51 (v0.97.28): Gain-Messung vereinheitlichen — 1 Messung,
2 Auswertungen, beide Stores atomar gespeichert. Mode-Wechsel Std↔DX wird
instant.

Bitte reviewe die geaenderten Files auf:
- Korrektheit (beide Auswertungen aus identischen _phase_data,
  Top-Level-Spiegel, Fallback bei has_dual=False)
- Bugs (Daten-Korruption wenn DX-Store mit Std-identischen Werten
  ueberschrieben wird? R1-V4-pro-F4 in V3 adressiert)
- KISS (Helper _best_for + _build_scoring_result OK? Overengineering?)
- Hardware-Pflicht ANT1=TX: unveraendert. set_tx_antenna("ANT1") in
  _finish bleibt.
- Adaptive-Stop OR-Logik (V3 AC7 bewusst akzeptiert)
- settings.save_dx_preset komplett raus (R1-F6 — get_dx_preset wird
  nirgends gerufen, tote API)

Bekannt:
- ROUNDS=2 × 2 Antennen × 2 Gain-Stufen = 8 Zyklen (nicht 18 wie urspruenglich
  geplant — Code-Wirklichkeit).
- Normal-Modus-Pfad in _on_dx_tune_accepted (Z.1483+) ist separat, ruft
  save_normal_preset (nicht angefasst).

Format: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
Antwort beginnt mit "Push freigegeben." oder konkretem Fix-Bedarf.
