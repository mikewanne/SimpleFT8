[deepseek] ~30448 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=34401 out=2224 total=36625
## Bewertung P47‑Implementierung (v0.97.11)

### 1. Korrektheit der 4 Änderungen + 5 Tests

| Änderung | Korrekt? |
|----------|----------|
| **config/settings.py**: `audio_freq_hz`/`max_decode_freq` aus DEFAULTS, Properties, `load()`-Pop mit `idempotent pop`, `get_normal_tx_freq`‑Fallback 1500 | ✅ Ja – sauber, keine Nebenwirkungen |
| **ui/settings_dialog.py**: Entfernen der zugehörigen UI‑Elemente (Hints, SpinBoxes, Form‑Rows, Load/Save/Reset) | ✅ Ja – vollständig und konsistent |
| **ui/main_window.py**: `Encoder(1500)`/`Decoder(max_freq=3000)` statt Settings‑Lookup; Entfernen von `_FILTERS`, `filter_str`, `"Filter:"-Segment` in der Statusbar | ✅ Ja – Hartkodierung entspricht den alten Defaults und war ohnehin wirkungslos |
| **Anpassung existierender Tests** (Smoke‑Stub, `_data = {}`-Tests) | ✅ Ja – werden mitgeliefert, kein Widerspruch |

**5 neue Tests in `test_p47_dead_freq_settings.py`**:
- T1 ✅ – alte Config-Keys werden beim Laden entfernt  
- T2 ✅ – keine Property `audio_freq_hz`/`max_decode_freq` mehr  
- T3 ✅ – Fallback `get_normal_tx_freq` = 1500  
- T4 ✅ – per‑band‑Einträge bleiben funktionsfähig  
- T5 ✅ – Source‑Code enthält die gelöschten Strings nicht mehr  

### 2. Bugs / Sideeffects

- **Keine erwarteten** – alle Änderungen sind streng dekorrelierbar, tote Einstellungen wurden sauber entfernt.  
- Potenzielle Risiken (z.B. externe Skripte, die auf `settings.get("audio_freq_hz")` zugreifen) sind **sehr gering**, da diese Keys nirgends mehr in der App referenziert werden.  
- Der `Decoder(max_freq=3000)` ist eine Konstante. Für FT2 (Default max_freq=4000) ändert sich nichts, da der Decoder ohnehin auf 3000 Hz lief (Bug‑Description). **Kein Funktionsverlust**.

### 3. KISS-Konformität

✅ **Erfüllt.**  
- Tote Einstellungen durch Konstanten ersetzt → weniger Code, weniger Fehlerquellen.  
- Statusbar‑Filteranzeige entfernt (irreführend) → reduziert UI‑Rauschen.  
- Idempotenz (pop mit Default) und hartkodierte Fallbacks folgen dem KISS‑Prinzip.

### 4. Verbleibendes Risiko

**LOW** (wie erwartet).  
- Keine Änderung an der Laufzeitlogik (Encoder/Decoder‑Verhalten bleibt identisch).  
- Die 5 Tests decken alle relevanten Aspekte ab.  
- Backup liegt vor – bei unerwarteten Problemen kann auf v0.97.10 zurückgerollt werden.

### 5. Push freigegeben?

✅ **Ja. 1162 → 1167 Tests grün, alle Änderungen dokumentiert und getestet.**  
- Commit‑Message enthält alle Details.  
- Backup existiert (siehe `AppSicherungen/2026-05-13_v0.97.10_vor_p47_dead_freq_settings/`).  

**Fazit:** Saubere, risikoarme Hygiene‑Änderung. Push freigegeben.
