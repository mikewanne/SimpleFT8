# R1-Review Request — Bundle C V2

Du bist DeepSeek-R1. **Pruefe diesen V2-Plan kritisch** — finde
Fehler, Luecken, Overengineering, fehlende Akzeptanzkriterien.

Antworte:
- KRITISCH (KP-N): wuerde Bug einfuehren
- SOLLTE-FIX (S-N): architektonisch problematisch
- KOENNTE (K-N): Optimierung
- HINWEIS (H-N): klein

Pro Finding: Datei:Zeile + konkrete Empfehlung.

Mike-Kontext:
- Hobby-Funker-Tool. KISS schlaegt Eleganz.
- Memory `feedback_partial_fix_check_other_paths.md`: bei Bug-Fix
  IMMER alle Pfade gleicher Klasse pruefen (V1 hat nur 1 von 2
  PSK-Pfaden gefixed — V2 zog nach).

## V2-Plan

[Inhalt von bundle_c_v2.md kommt nach]

## Konkrete Pruefauftraege

1. **P10 Fix-B Statusbar-Pfad — Race mit laufendem `_psk_worker`-
   Thread?** `_on_band_changed` triggert `_psk_timer.start(0)`
   waehrend eventuell noch ein Worker-Thread im Fetch ist. Was kann
   passieren? Wuerde das `update_psk_stats(...)` doppelt rufen mit
   gemischten Band-Werten (alt + neu)?

2. **P10 BACKOFF_MAX_S = 600s** — zu aggressiv? Bei laenger
   andauerndem PSK-Server-Outage (z.B. 30 Min Wartung) wuerden
   10-Min-Polls 3x stattfinden statt 1x bei 60-Min-Cap. Last-Risiko
   fuer PSK-Server? V2 begruendet das mit „Hobby-Session 1-3
   Stunden" — ist das ausreichend?

3. **P10 reset_backoff() Thread-Safety** — V2 sagt „CPython GIL
   macht es atomar". Stimmt das wenn `_run_loop` mit
   `self._backoff.current_s * self.factor` rechnet (Z.158)? Das ist
   read-modify-write. Wenn `reset_backoff()` zwischen read und
   write feuert, koennte das alte Werte zurueckschreiben.

4. **P10 — `_psk_worker` als Thread vs `_psk_timer` als QTimer**.
   `_psk_timer.start(0)` ist Qt-Timer und feuert im GUI-Thread.
   Aber `_psk_worker` wird in `_fetch_psk_stats` (Z.940+) als
   `threading.Thread(daemon=True).start()` aufgerufen. Funktioniert
   `_psk_timer.start(0)` synchron oder asynchron? Wann genau startet
   der Thread?

5. **P10 — Mike-Anforderung 3 (Auto-Reset bei OMNI-Start)** wurde
   verworfen. Plausibel? OMNI-Start ist eigentlich der haeufigste
   Trigger fuer „App-Session-Start" bei Mike's Hobby-Workflow.
   Sollte OMNI-Start auch `reset_backoff()` + `_psk_timer.start(0)`
   triggern? Oder ueberkomplex?

6. **P13 — Slot-Boundary-Berechnung in rx_panel**: V2 zeigt
   `time.strftime("%H%M%S", time.gmtime(slot_ts))`. Wenn
   `slot_ts` ein Float ist mit Sub-Sekunden-Komponente (z.B.
   1715000000.234), wirft `gmtime` darauf eine struct_time mit
   Sekunden gerundet. Bei FT8 sollte slot_ts immer auf 0/15/30/45
   liegen — wenn Decoder genauer ist, bekommt rx_panel falsch
   gerundete Werte. Pruefen.

7. **P13 — Sort-Ordnung Aenderung**: Bisher Wall-Time (10:51:42),
   neu Slot-Boundary (10:51:30). Was passiert wenn das Sort-Feld
   sich aendert? Bestehende Eintraege im rx_panel sind mit
   Wall-Time eingefuegt, neue mit Slot-Boundary. Im selben Zyklus
   wird Sort durcheinander geraten. Loesung: vollstaendiges Repaint
   nach Codedeploy oder Migration der Bestandseintraege?

8. **P13 Settings/rx_history_store**: V2 sagt „nicht betroffen".
   Pruefen: speichert rx_history_store auch UTC-Zeile? Wenn ja:
   bei App-Restart kommen alte Eintraege mit Wall-Time, neue mit
   Slot-Boundary — User sieht 2 unterschiedliche Formate
   nebeneinander.

9. **Bundle-Strategie OK?** P10 + P13 sind unabhaengig, beide klein.
   2 atomare Commits + 1 Doku ok? Oder zu viel Trennung?

10. **Backup-Strategie**: V2 nennt 3 Files (`psk_reporter.py`,
    `mw_radio.py`, `rx_panel.py`). Sind das alle? `main_window.py`
    wird nicht angefasst — sicher?

## Antwort-Format

```
KP-N: ...
S-N: ...
K-N: ...
H-N: ...

ZUSAMMENFASSUNG:
- KRITISCH: X
- SOLLTE: X
- Plan-Status: [Push freigegeben | V3 noetig | grundsaetzlich neu]
```
