[deepseek] ~34054 Tokens, 4 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=38026 out=1745 total=39771
## Optionenvergleich

| Option | UX | Aufwand | Risiken |
|--------|-----|---------|---------|
| **A – Nur FT8 misst** | Schlicht: FT4/FT2 nutzen stets den (auch alten) Bandwert. Einmaliger Hinweis bei Erstnutzung ohne Wert. Kein Unterbrechen. | **Klein** (≤3 Dateien: `preset_store.py` Key-Logik, `mw_radio.py` _check_diversity_preset, ggf. Statusbar-Hinweis). Kaum neue Pfade. | Veralteter Gain bei reiner FT4/FT2-Nutzung möglich – physikalisch unkritisch (Antenne ändert sich nicht sprunghaft). Nur bei Erstinstallation ohne FT8-Messung kurze Verwirrung: Nutzer muss kurz auf FT8 wechseln. |
| **B – Auto-Switch zu FT8** | Komplex: Modus-Flicker, QSO-Unterbrechung möglich, Nutzer versteht nicht warum Modus wechselt. | **Groß** (State-Restore nach Mode-Wechsel, Pipeline-Lock, TX-Stop mitten in QSO, erneute _enable_diversity, Timer, OMNI/Auto-Hunt-Abbruch). Viele Race-Conditions und Testfälle. | Moduswechsel während aktiver QSO gefährdet Datenverlust. Restore von Frequenz, Slot-Lock, CQ-Status komplex und fehlerträchtig. Encoder-Race: Ungetriggerte TX-Slots nach Rückkehr. Aufwand lohnt nicht für seltenen Fall. |

## Empfehlung

**Option A ist der klare KISS-Weg.** Der physikalische Gain ist eine Antenneneigenschaft pro Band und driftet nicht über Stunden oder Tage. Die 6-Stunden-Frist für FT8 ist schon konservativ; FT4/FT2 können ohne Bedenken jedes vorhandene Band-Gain nutzen, selbst wenn es älter ist. Ein passiver Hinweis (Statusbar, einmaliger Info-Dialog mit „Nicht mehr anzeigen“) genügt für den unwahrscheinlichen Fall, dass noch nie eine Messung auf diesem Band erfolgte. Option B schießt mit Kanonen auf Spatzen: Sie löst ein Problem, das es praktisch nicht gibt, und bringt erhebliche Stabilitätsrisiken durch programmatische Moduswechsel während des Betriebs. Mikes Philosophie „KISS schlägt Vollständigkeit“ spricht klar für A. _Gain-Messung ist ein Setup-Schritt, der typischerweise beim ersten Start auf einem Band in FT8 erledigt wird – danach ist der Wert da und alle Modi profitieren._
