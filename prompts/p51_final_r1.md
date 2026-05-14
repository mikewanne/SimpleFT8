[deepseek] ~32449 Tokens, 4 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=36019 out=8408 total=44427
Push freigegeben.

| Schwere | Finding | Datei:Zeile | Empfehlung |
|---------|---------|-------------|------------|
| INFO | Kommentar im `_build_interleaved_schedule` spricht von 12 Einträgen, es sind aber nur 8 (2 Runden × 2 Antennen × 2 Gain-Stufen). | ui/dx_tune_dialog.py:40 | Kommentar anpassen („8 Schritte“ oder entfernen), um Verwirrung zu vermeiden. |
| INFO | `_build_scoring_result` bestimmt die beste Antenne (`best_ant`) anhand des SNR-Mittelwerts (`a1["avg"] >= a2["avg"]`), auch wenn `use_snr=False` (Standardmodus). Für den Standardmodus könnte die Stationsanzahl relevanter sein, aber beide Antennen werden ohnehin im Diversity genutzt – funktional harmlos. | ui/dx_tune_dialog.py:338–348 | Optional: Für den Standardmodus `best_ant` nach Stationsanzahl oder gar nicht ausgeben, aber das Verhalten ist legacy und kann bleiben. |
| INFO | In `_on_dx_tune_accepted` werden bei has_dual=True auch im Normalmodus beide Diversity-Stores (`_standard_store` / `_dx_store`) geschrieben, zusätzlich zu `save_normal_preset`. Das ist durch P51 intendiert (sofortiger Std↔DX‑Wechsel möglich), könnte aber User überraschen, die nur normal kalibrieren wollen. | ui/mw_radio.py:1453–1477 | Keine Änderung nötig; Verhalten ist explizit gewollt. Bei Bedarf könnte ein Hinweis in der UI ergänzt werden („Presets für Diversity wurden ebenfalls aktualisiert“). |

**Zusammenfassung:** Die P51‑Änderungen arbeiten korrekt, die zwei Auswertungen aus demselben `_phase_data` werden atomar in beide Stores geschrieben, und die Fallback‑Logik bei `has_dual=False` verhindert Daten‑Korruption. Die Helfer `_best_for` und `_build_scoring_result` sind schlank und passend. Adaptiv‑Stop, TX‑Härtung und das Entfernen der toten `save_dx_preset`‑API sind wie gefordert umgesetzt. Keine schwerwiegenden Bugs. `Push freigegeben.` ist angemessen.
