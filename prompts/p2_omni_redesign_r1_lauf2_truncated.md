[deepseek] ~45616 Tokens, 5 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=51372 out=8000 total=59372
| Schwere | Finding | Datei/Zeile (Prompt) | Empfehlung |
|---------|---------|----------------------|-------------|
| 🔴 Bug | `_resume_cq_if_needed` (Timeout/QSO-Ende) ruft `_send_cq()` auf, das durch `auto_cq_enabled=False` blockiert wird. → State bleibt hängen, OMNI-Loop tot | Geplante Änderung, Punkt 1 + Root Cause | `_resume_cq_if_needed` muss bei aktivem OMNI entweder `auto_cq_enabled` temporär setzen oder den OMNI-Treiber direkt triggern (z. B. `qso_sm._omni_drive_cq(…)`). |
| 🔴 Bug | Nach QSO-Ende (z. B. nach TX_73_COURTESY) wird `_resume_cq_if_needed` aufgerufen, `_send_cq` ignoriert → state bleibt TX_73_COURTESY oder LOGGING, nicht IDLE/CQ_WAIT → `omni_drive_cq` kann nicht feuern | Akzeptanzkriterium 5 + Geplante Änderung Punkt 1 | `_resume_cq_if_needed` muss state explizit auf `CQ_WAIT` oder `IDLE` setzen, wenn kein CQ gesendet wird (z. B. `self._set_state(Q
