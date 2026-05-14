[deepseek] ~50972 Tokens, 7 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=57207 out=3151 total=60358
Push freigegeben.  
Bundle J (v0.97.27) ist sauber umgesetzt: Der Footer erscheint im Connect-Modal, der einheitliche Help-Dialog mit Scrollbar verhält sich korrekt, die `_antenna_pref_label`-Anpassung zeigt `RX:`-Präfix nur bei ANT2, und die Intent-Klausel ist im Hardware-Disclaimer verankert. Keine Bugs, kein Threading‑/Race‑Problem, keine Verletzung der Hardwarevorgabe. Die Tests decken alle neuen Pfade ab.

---

| Schwere | Finding | Datei : Zeile | Empfehlung |
|---------|---------|---------------|------------|
| 🔴 (Bug) | *keine* | – | – |
| 🟠 (Risiko) | *keine* | – | – |
| 🟡 (Verbesserung) | ConnectStatusDialog könnte nach `exec()` explizit mit `deleteLater()` entsorgt werden, um das C++‑Objekt sofort freizugeben und Memory kurz zu halten. | `ui/mw_radio.py` nach `_connect_dialog.exec()` | `self._connect_dialog.deleteLater()` am Ende des Blocks |
| 🟡 (Verbesserung) | `QTextBrowser` rendert Markdown; bei sehr großen Hilfedateien könnte das Rendering im Haupt‑Thread minimal blockieren. Für die ~20 KiB‑Dateien derzeit unkritisch. | `ui/simple_help_dialog.py` | Bei Bedarf später asynchrones Laden in Betracht ziehen. |
| 🔘 (Hinweis) | `_make_info_btn` öffnet jetzt einen skalierenden 700×600‑Dialog, auch wenn der Hint nur eine kurze Zeile ist. Das entspricht explizit Mikes Konsistenz‑Designwunsch (TODO J‑2). Keine Meldung nötig. | `ui/settings_dialog.py: _make_info_btn` | – |
| 🔘 (Hinweis) | Footer‑Höhe wurde von 176 auf 196 px erhöht; der Knopf‑Zeilen‑Abstand könnte auf sehr kleinen macOS‑Auflösungen knapp sein, ist aber für 1440×900 und höher passend. | `ui/connect_status_dialog.py: setFixedSize(352, 196)` | – |
