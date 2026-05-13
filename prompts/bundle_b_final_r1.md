[deepseek] ~52763 Tokens, 7 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=60060 out=2521 total=62581
## Zusammensfassung der Findings

| ID | Typ | Datei:Zeile | Finding | Empfehlung |
|----|-----|-------------|---------|------------|
| **S-1** | SOLLTE-FIX | `ui/mw_qso.py:242-243` | `_on_rx_hidden_cols_changed` ruft `self.settings.save()` ohne Fehlerbehandlung. Bei Disk voll / Permissions → Exception steigt hoch und blockiert GUI-Ereignis (Slot wird unterbrochen, `hidden_cols`-Puffer inkonsistent). | `settings.save()` mit `try/except` schützen und ggf. `print` ins Debug-Log. Analog zu anderem `save()` im Bundle A. |
| **K-1** | KOENNTE | `ui/qso_panel.py:91` / `ui/mw_qso.py:496-535` | `add_qso_complete` wird nur in `_on_qso_confirmed_visual` aufgerufen. **Gibt es noch andere Aufrufer?** (z.B. ältere `_on_qso_complete`-Pfade in `mw_qso.py`?) – In den bereitgestellten Dateien keine, aber vollständiges Projekt nicht einsehbar. | Kurzes `grep -rn "add_qso_complete" src/` im realen Repository durchführen, um sicherzustellen, dass kein zweiter Pfad existiert. |
| **K-2** | KOENNTE | `tests/test_p1_10_courtesy_73.py` (nicht sichtbar) | Bestehende Tests könnten auf `qso_confirmed.emit` lauschen und jetzt `qso_confirmed_visual` erwarten – `1204 passed` deutet auf Kompatibilität, aber Risiko bei zukünftigen Änderungen. | Falls existierende Tests `qso_confirmed.emit` direkt testen, sollten sie auf `qso_confirmed_visual` angepasst werden (oder beide Signale testen). |
| **Keine Kritischen** | | | Alle Prüfpunkte 1–4, 7–9 zeigen keine sicherheitskritischen Bugs. Reihenfolge, Doppelschutz und Single‑Thread‑Garantie sind korrekt umgesetzt. | – |

## Push‑Freigabe

**Status: FREIGEGEBEN mit den obigen SOLLTE‑ und KÖNNTE‑Hinweisen.**

Das Bundle B’ kann gemerged werden, sobald S‑1 gefixt ist (ca. 10 Minuten). K‑1 und K‑2 sind optional vor dem Merge – sie erhöhen die Absicherung, sind aber nicht blockierend.
