[deepseek] ~9972 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=11925 out=4124 total=16049
## Diskussion zu Mike's Vorschlag – Diversity-Cache-Reuse beim Bandwechsel

### 1. Cache-Validity X: 2 Stunden – begründet

Als Funker: Die Ratio auf einem Band ändert sich selten innerhalb weniger Stunden, **es sei denn**, die Tageszeit überschreitet eine Dämmerungsgrenze (z.B. 18–20 UTC im Sommer auf 20m/40m).  
- **2h** deckt eine typische Hobby-Session sicher ab, fängt aber Dämmerungsübergänge noch ab.  
- **4h** wäre auch vertretbar, erhöht aber das Risiko, z.B. wenn jemand von 15–19 UTC funkt – zwischenzeitlich kann sich das Bandverhalten drehen.  
- **6h (PresetStore-Validity)** ist zu lang – zu viele Edge-Cases (Tag→Nacht, Saisonwechsel).  

Mein Vorschlag: **2h Default**, ggf. einstellbar in den Settings für Power-User. Das ist konservativ und bewahrt den Kompromiss zwischen Zeitersparnis und Aktualität.

### 2. Tageszeit-Variation – du überschätzt das Risiko nicht

Deine Bedenken sind berechtigt. Allerdings:  
- Das Antennenverhältnis (z.B. Dipol vs. Vertikal) ist **hardware-getrieben** und ändert sich nur langsam.  
- Starke Schwankungen treten vor allem bei **Bandwechsel (z.B. 20m↔40m)** auf, weil dort andere Ausbreitungsmodi dominieren. Innerhalb eines Bandes ist die Ratio oft über 2–3h stabil.  
- Die v0.90-Statistik (fair 3:3) wird zeigen, ob der Bias wirklich so stark ist wie pre-v0.90. Aber selbst wenn nicht: Die 2h-Grenze fängt temporäre Ausreisser (z.B. Contest-Spitze, Sonnenfinsternis) nicht ab – das ist aber ein seltener Fall.  

Fazit: Risiko nicht überschätzt, aber auch nicht vernachlässigbar. Mit 2h und UI-Hinweis gut handhabbar.

### 3. Schlimmster Edge-Case und Erkennbarkeit

**Schlimmster Fall:**  
Mike wechselt von 20m (wo A1 mit 70:30 dominant) auf 40m. Der Cache für 40m ist 5h alt und stammt aus der Nacht (A2 dominant, z.B. 30:70). Jetzt ist aber Tag, und A1 wäre besser. Er funkt 15 Minuten mit suboptimaler Ratio, verpasst Decodes.

**Wie merkt Mike das?**  
- Er vergleicht nicht aktiv, aber die **QSO-Rate sinkt** spürbar (weniger Stationen decodiert, schlechtere SNR-Anzeige).  
- **UI-Feedback** ist hier kritisch: Toast „Diversity aus Cache (3h alt)" gibt ihm die Möglichkeit, manuell ein Re-Measure zu triggern oder den Cache zu ignorieren.  
- Wenn er den Hinweis ignoriert, ist es sein Problem – das Risiko ist akzeptabel.

Ein automatischer **Fallback** wäre denkbar: Nach 10 Operate-Zyklen mit Cache-Ratio die Performance tracken (z.B. Anzahl decodierter Stationen vergleichen mit erwartetem Wert aus dem Cache-Zeitraum). Das wäre aber Overengineering. KISS reicht: Toast reicht.

### 4. Auto-Refresh alle 80 Zyklen – nicht nötig

Der aktuelle Betrieb hat bereits einen **Re-Measure-Zyklus alle 60 Zyklen** (≈15 Min). Dabei wird die Ratio neu gemessen und im PresetStore gespeichert (`save_ratio`). Das aktualisiert den Cache automatisch.  
- Der Vorschlag „80 Zyklen" ist quasi der gleiche Mechanismus (nur etwas später). Wir sollten **den bestehenden Re-Measure-Zyklus verwenden**, nicht einen separaten Timer.  
- **Kein zusätzlicher Code** nötig – der Re-Measure speichert bereits. Das ist KISS.

Falls Mike explizit meint, dass der Cache auch ohne Messung „erfrischt" werden soll (z.B. Timestamp auf `now` setzen, ohne Messung): Das wäre gefährlich, weil der Cache dann neu aussieht, aber die Werte stimmen nicht mehr. **Explizit nur bei tatsächlicher Messung aktualisieren**.

### 5. Ist der Aufwand die Mühe wert? – Ja, aber mit Augenmaß

- Aktuelle Pipeline-Dauer nach Block 1: ~4:31 Min (inkl. Gain-Messung).  
- Nach Block 2 (Gain gültig): ~3:20 Min (nur Phase 3).  
- Ein Bandwechsel kostet also mindestens 3–4 Minuten Wartezeit. Bei 2–3 Wechseln pro Session sind das **6–12 Minuten** eingespart, wenn der Cache gültig ist.  

Für einen Hobby-Funker ist das relevant. Die Code-Änderung ist **klein**:
- In `_on_band_changed` einen Cache-Check einbauen (bestehende `PresetStore.is_valid`/`get` nutzen).  
- Falls gültig → `diversity_ctrl` mit gespeicherter Ratio initialisieren, Phase auf operate setzen, Phase 3 überspringen.  
- UI-Feedback einbauen.  
- Regression-Test anpassen (`test_load_preset_removed` umlabeln oder erweitern – nicht löschen, sondern band-spezifischen Reuse erlauben).  

**Aufwand:** ca. 1–2 Stunden inkl. Tests. Das ist vertretbar.

### 6. KISS / Overengineering

Der Vorschlag ist **nicht overengineered**. Er nutzt bestehende Infrastruktur (`PresetStore`, `DiversityCache`) und fügt eine einfache Prüfung hinzu. Keine neuen Abstraktionen, keine zusätzlichen Timer.  

- **Gegenbeispiel:** Ein automatisierter Performance-Vergleich, der den Cache ungültig macht, wenn die Decoderate sinkt – das wäre Overengineering.  
- **So, wie Mike es vorschlägt:** Einfach, direkt, nachvollziehbar. Passt zu KISS.

Einzige Vorsicht: Der **v0.74-Fix** war nötig, weil damals der Cache nicht band-spezifisch war. Jetzt sind wir an dem Punkt, band-spezifische Caches zu haben. Der Fix ist nicht mehr verletzt. Also **grünes Licht**.

---

**Gesamtbewertung:**  
- **Cache-Validity: 2h**  
- **Auto-Refresh: nicht nötig** (bestehender Re-Measure-Zyklus reicht)  
- **Mühe wert: Ja**  
- **KISS: Passt**  
- **Risiko: Beherrschbar mit UI-Timeout und manuellem Override**

Ich würde Mike empfehlen: **Mach es, aber halte den Cache-Validitätscheck einfach und dokumentiere die UI-Meldung. Und denk dran: Der alte Regression-Test muss umgeschrieben werden, nicht einfach gelöscht.**
