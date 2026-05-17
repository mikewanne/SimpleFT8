[deepseek] ~30973 Tokens, 3 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=35797 out=2209 total=38006
Die Re‑Entry‑Sperre in `_tune_stop` ist korrekt umgesetzt.  
Ein neues Flag `_tune_stop_active` wird zu Beginn auf `True` gesetzt, bevor die kritische Phase B (Closed‑Loop‑Convergenz) gestartet wird, und am Ende wieder auf `False` zurückgesetzt. Ein paralleler Aufruf (z. B. durch User‑Cancel via Qt‑Sub‑Event‑Loop) erkennt das aktive Flag, setzt stattdessen `_tune_convergence_cancelled=True` und kehrt sofort zurück – ohne `tune_off` doppelt auszuführen. Die Original‑Instanz von `_tune_stop` prüft dieses Cancel‑Flag in der Convergenz‑Schleife und bricht diese ab, sodass anschließend nur ein einziges `tune_off` erfolgt.

Der Test T19 bildet dieses Szenario mit einem Mock‑Objekt ab: `_tune_stop_active = True` und `_tune_active = True`, Aufruf mit `token=None`. Er verifiziert, dass `tune_off` nicht aufgerufen und `_tune_convergence_cancelled` auf `True` gesetzt wird – exakt das spezifizierte Verhalten.

Die Initialisierung von `_tune_stop_active` (in `_init_diversity_state`) und das Zurücksetzen nach der Convergenz sind vorhanden. Es fehlt nichts; die Re‑Entry‑Sperre ist vollständig und durch den Test abgedeckt.
