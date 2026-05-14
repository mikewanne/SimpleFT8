[deepseek] ~56981 Tokens, 6 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=63474 out=8054 total=71528
| Schwere | Finding | Datei:Zeile | Empfehlung |
|---------|--------|-------------|------------|
| 🔴 Bug | `RadioInterface`-ABC enthält keine abstrakte `set_swr_limit`-Methode (AC12 verlangt dies) | `radio/base_radio.py` (gesamte Klasse) | `@abstractmethod set_swr_limit(value: float) -> None` hinzufügen |
| 🔴 Bug | `_swr_spike_count` wird im gesamten Code nirgends initialisiert – der erste Zugriff in `_on_swr_alarm` führt zu einem `AttributeError` | `ui/mw_tx.py` (Mixin `TXMixin`) bzw. MainWindow‑`__init__` | `self._swr_spike_count = 0` im Konstruktor (vor dem ersten möglichen Alarm) setzen |
| 🟠 Risiko | AC1 fordert einen Mindestabstand von ≥ 100 ms zwischen zwei Alarm‑Emits, während die Implementierungsskizze diese untere Schranke bewusst weglässt → bei sehr kurz aufeinanderfolgenden Emits (< 100 ms) würde ungewollt der Stop‑Block ausgeführt | AC1 / „Spike‑Schutz“-Abschnitt im Prompt | Entweder AC1 anpassen (untere Schranke entfernen) oder im `_on_swr_alarm` doch `>= 0.1` prüfen |
| 🟠 Risiko | `settings_dialog._save_and_close()` propagiert den geänderten SWR‑Grenzwert nicht an das verbundene Radio – AC10 ist nicht implementiert | `ui/settings_dialog.py` in `_save_and_close` (ca. Z. 679) | `parent.radio.set_swr_limit(… )`-Aufruf ergänzen, wenn `parent.radio.ip` gesetzt ist |
