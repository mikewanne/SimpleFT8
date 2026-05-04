[deepseek] ~36798 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=41914 out=5409 total=47323
## Bewertung des Refactor-Vorschlags (Mike's Vision)

**Auftrag:** Fachliche, KISS-orientierte Diskussion – kein Code.

---

### A) Zeit-basiertes Re-Measure

1. **1 h Auto-Refresh – vernünftig?**  
   Ja. 15-Min-Zyklen sind für Hobby-Use zu aggressiv (ständige Messungen). 1 h ist ein guter Kompromiss: spart Unterbrechungen, reduziert Verschleiß bei Relais. Tag/Nacht-Übergang (17–19 UTC) kann die Ratio innerhalb 1 h kippen – das ist ein inhärentes Problem jeder festen Frist. 1 h korrigiert aber schneller als 2 h. Empfehlung: **1 h beibehalten.**

2. **Time-based vs. cycle-based – Vorteile/Nachteile?**  
   Vorteile: physikalisch korrekter (Bedingungen ändern sich zeitlich, nicht nach Zyklen); keine Modus-abhängige Skalierung nötig; einfachere Implementierung (`time.time()`).  
   Nachteile: NTP-Sprünge (vernachlässigbar), Suspend/Resume (time läuft weiter – nach Aufwachen >1 h → sofortige Messung, aber Lock schützt).  
   Fazit: **KISS-Verbesserung.**

3. **QSO-Lock + CQ-Lock?**  
   QSO-Lock existiert. CQ-Lock fehlt in `should_remeasure`. Während CQ-Ruf soll nicht gemessen werden (TX-Slots gebraucht). Erweiterung um `cq_active`-Flag ist nötig und einfach. **Empfehlung: CQ-Lock hinzufügen.**

---

### B) Pro-Band-Cache

4. **1 h Validity – richtig?**  
   Aus Konsistenzgründen (gleiche Frist wie Auto-Refresh) **ja**. 2 h wären auch okay, aber 1 h ist klarer. Nachteil: etwas mehr Re-Measures (ca. 4 pro 4h-Session vs. 2 bei 2h). In der Praxis irrelevant.

5. **5-s-Toast ohne User-Interaktion – ausreichend?**  
   Ja. Non-modal, informiert ohne zu stören. Optionaler „Neu messen“-Button im Toast wäre Nice-to-have, aber nicht KISS.

6. **Schreibverhalten – separater Save-Pfad nötig?**  
   Nein. Cache wird nach jeder vollständigen 6-Zyklen-Messung überschrieben – das ist konsistent. Einzige Sorge: gleichzeitiger Bandwechsel und Auto-Refresh – durch Lock entschärft.

---

### C) Normal-Modus raus

7. **Sinnvoll?**  
   Ja. Normal-Modus hat keine automatische Ratio-Steuerung – Caching wäre sinnlos. Die Aussage „andere Software macht das auch nicht“ ist zutreffend. KISS-Argument: weniger Pfade.

8. **Konsequenz: manuelle Kalibrierung speichert nicht – akzeptabel?**  
   Ja. Der NEU-Button löst eine volle Pipeline aus (Tune+Gain+Measure). Ratio wird nicht gespeichert – das ist der aktuelle Zustand für Normal. User muss bei App-Start klicken – akzeptabel für Hobby-Tool.

---

### D) Konstanten-Cleanup

9. **`OPERATE_CYCLES` entfernen – Risiko?**  
   Die Konstante wird in `_enable_diversity` überschrieben und in `mw_cycle.py` für UI-Anzeige verwendet (`operate_total`). Mit zeitbasiertem System muss die UI auf `(3600 - age) / cycle_duration` umgestellt werden. **Machbar, geringes Risiko.**

10. **`_MULT` entfernen – betrifft auch MEASURE_CYCLES (V2 Finding 1).**  
    **Kritisch.** Für FT4/FT2 sind 6 Zyklen zu kurz (FT2 = 23 s). Die statistische Basis wäre zu dünn.  
    **Empfehlung:**  
    - `_MULT` für `MEASURE_CYCLES` **behalten** (FT8=6, FT4=12, FT2=24).  
    - Für `OPERATE_CYCLES` kann `_MULT` entfallen, da zeitbasiert.  
    Mike's Vision sollte hier **modifiziert** werden.

11. **Settings-Option `diversity_operate_cycles` entfernen – akzeptabel?**  
    Ja. Hobby-Tool, KISS. Die 1h-Frist ist fest – kein Tuning nötig.

---

### E) Edge-Cases

12. **Cache knapp unter 1h + Tag/Nacht-Wechsel**  
    Ist akzeptabel. Auto-Refresh korrigiert spätestens nach 5 Minuten (bei 1h). Das Fenster suboptimaler Ratio ist kleiner als bei 2h Validity.

13. **Fehlende Stationen für Re-Measure**  
    Aktuell wird `_evaluate` immer ausgeführt, auch mit `station_count=0` → 50:50. Das bleibt so – robust.

14. **App Suspend/Resume**  
    `time.time()` läuft weiter → Cache >1h → sofortige Messung beim Aufwachen. QSO-Lock schützt. **OK.**

---

### F) KISS-Bewertung

15. **Vereinfachung oder neue Komplexität?**  
    Netto-Vereinfachung: weniger Konstanten, keine Zyklen-Zählerei, keine Modus-Multiplikatoren für Operate. Cache-Reuse-Logik ist überschaubar (Prüfung + Toast). **Klare Vereinfachung.**

16. **Fix-Aufwand: Mike's Vision (3–5 h) vs. MINI (1–2 h)**  
    MINI wäre weniger invasiv, führt aber zu zwei parallelen Systemen (zeitbasiert für Re-Measure, zyklenbasiert für Operate). Das ist nicht KISS.  
    **Empfehlung: Mike's Vision umsetzen** – in der modifizierten Form (siehe G17/G18).

---

### G) Code-Migration (V2)

17. **`MEASURE_CYCLES`-Skalierung behalten oder entfernen?**  
    **Behalten.** FT4/FT2 benötigen längere Messzeit für statistische Zuverlässigkeit. Mike's Vision komplett entfernen = too much.

18. **PresetStore-Timestamp: 1 oder 2?**  
    **Zwei Timestamps.** Aktuell überschreibt `save_ratio` den timestamp nicht – das ist ein Problem: Ratio könnte frisch sein, der Timestamp aber alt (von Gain) → Cache würde fälschlich als ungültig betrachtet.  
    KISS: `ratio_timestamp` und `gain_timestamp` (oder `timestamp` für Gain und `ratio_ts` für Ratio). `is_valid` checkt dann je nach Typ.

19. **App-Start mit Cache – Phase 3 überspringen?**  
    Ja. Bei Suspend/Resume ist der Cache typischerweise >1h → wird neu gemessen. Risiko bei Crash: serialisierte Timestamps sind zuverlässig.

20. **Tests-Migration**  
    Einfach: Mock-PresetStore + Aufruf von `_on_band_changed`. Prüfung, ob `_diversity_ctrl.phase` nicht auf „measure“ gesetzt wurde.

---

### H) UX-Edge-Cases

21. **5-s-Toast Sichtbarkeit**  
    Reicht. Bei schnellen Bandwechseln (Bandpilot) könnte der Toast mehrfach erscheinen – das ist informativ, nicht störend.

22. **Cache-Reuse + Auto-Hunt**  
    Auto-Hunt wird ca. 1 Minute früher aktiv – positiv.

---

## Gesamtempfehlung

**Mike's Vision umsetzen – mit folgenden Modifikationen:**

- `_MULT` für `MEASURE_CYCLES` **behalten** (FT8=6, FT4=12, FT2=24).  
- PresetStore: **zwei Timestamps** (`gain_timestamp`, `ratio_timestamp`).  
- CQ-Lock in `should_remeasure` ergänzen.

**Begründung:**  
- Weniger Konstanten → klareres Code-Modell.  
- Zeitbasiert = physikalisch korrekt.  
- Ratio-Cache spart bei Bandwechseln 1 Minute.  
- Normal-Modus bleibt schlank.  
- FT4/FT2 werden nicht benachteiligt.

**Abgrenzung zu MINI:** MINI wäre schneller, aber langfristig inkonsistent (zwei Systeme = mehr Komplexität). Der vollständige Refactor ist KISS-konform und lohnt den Aufwand.

**Geschätzter Mehraufwand:** ~4 h (inkl. Timestamp-Umbau und Tests), gut investiert.
