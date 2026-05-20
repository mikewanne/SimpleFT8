# P92 — Diversity-Sub-Toggle auch bei Bandpilot=AN

## 1. Ziel

Im Diversity-Modus soll der 2. Klick auf den DIVERSITY-Button **immer**
einen direkten Toggle Standard ↔ DX auslösen — unabhängig davon, ob
Bandpilot in Settings auf `off`, `auto` oder `manual` steht.

Mike-Begründung: Bandpilot soll eine Empfehlung sein, kein Zwang. Der
User muss seinen Diversity-Sub-Modus jederzeit manuell überstimmen
können (analog zum bereits funktionierenden Wechsel NORMAL ↔ DIVERSITY).

Heute ist der Sub-Toggle bei `bandpilot_mode != "off"` gesperrt
(`ui/mw_radio.py:895-897`). User muss heute den Umweg:
DIVERSITY-DX → NORMAL → DIVERSITY → Wahl-Dialog → STANDARD nehmen.

## 2. Akzeptanzkriterien

- **AC1** `_on_diversity_subtoggle_requested` toggled Std↔DX bei allen
  drei Bandpilot-Modi (`off` / `auto` / `manual`), solange Radio
  verbunden und Pipeline-Lock frei.
- **AC2** Bandpilot bleibt nach dem manuellen Override beim **nächsten
  Bandwechsel** automatisch wieder aktiv (kein Override-Persistenz-
  State, kein neuer „pause"-Flag).
- **AC3** Im Sub-Toggle-Pfad weiterhin OMNI + Auto-Hunt stoppen (R1-K1+K2
  aus Bundle G — verhindert Encoder-Konflikt und Histogramm-Race).
- **AC4** Pipeline-Lock (`_gain_measure_locked`) und fehlende Radio-IP
  blocken weiterhin (Hardware-Sicherheit).
- **AC5** Existierende Bundle-G-Tests (`tests/test_bundle_g_*.py`)
  bleiben grün — bzw. werden angepasst auf neues Verhalten.
- **AC6** Neue Tests T1-T4: Sub-Toggle in jedem `bandpilot_mode`
  (off/auto/manual) + Pipeline-Lock + radio.ip=None blockt weiter.

## 3. Betroffene Module/Dateien

- `ui/mw_radio.py:879-909` `_on_diversity_subtoggle_requested` —
  Block-Klausel Z.895-897 entfernen, Docstring aktualisieren.
- `tests/test_bundle_g_*.py` — Tests die `bandpilot_mode != "off"`
  als Block-Fall asserten umschreiben.
- `tests/test_p92_*.py` — NEU, 4 Tests.
- `main.py` — `APP_VERSION` 0.97.61 → 0.97.62.
- `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md`, `TODO.md` (Standard-Update).

## 4. Randbedingungen

- **Threading:** Slot läuft im GUI-Thread, kein Lock nötig.
- **Hardware:** Sub-Toggle löst keinen TX aus (nur RX-Mode-Wechsel).
  `_activate_diversity_with_scoring` ruft am Ende ggf. eine Gain-
  Messung an die ANT1=TX verlangt — bleibt unverändert, das ist nicht
  neuer Pfad.
- **State:** Bandpilot ist stateless bzgl. User-Overrides — bei jedem
  Bandwechsel ruft `_on_band_changed → _maybe_apply_bandpilot(band)`
  auf, das überschreibt den Modus automatisch wenn `bp_mode != "off"`
  und eine Empfehlung vorliegt. ✅ Mike-Anforderung erfüllt ohne neuen
  Code.
- **UX:** Kein neuer Dialog, kein Toast — User klickt, Toggle passiert
  ohne Rückfrage (analog Bundle G off-Pfad).
- **CLAUDE.md Hardware-Pflicht:** ANT1 = TX. Nicht betroffen, kein TX.

## 5. Nicht im Scope

- **Bandpilot-Logik selbst:** Empfehlungsalgorithmus, Toast/Dialog,
  Statistik-Aggregation bleiben unverändert.
- **Override-Persistenz:** kein „remember last manual choice"-Feature
  (Mike will explizit, dass Bandpilot beim nächsten Bandwechsel wieder
  übernimmt).
- **Bundle-H-Pfad** (Klick NORMAL → DIVERSITY): bleibt komplett wie
  heute (Toast/Manual-Dialog bei bp=auto/manual). P92 betrifft nur den
  2. Klick (Sub-Toggle innerhalb Diversity).
- **Auto-Hunt / OMNI Logik:** nur weiter-stoppen wie heute, keine
  Änderung am Stop-Mechanismus.

## 6. Testbarkeit

- **T1** Sub-Toggle bei `bandpilot_mode="off"` — vorhandenes Bundle-G-
  Verhalten bleibt grün.
- **T2** Sub-Toggle bei `bandpilot_mode="auto"` — toggled jetzt (vorher
  No-Op).
- **T3** Sub-Toggle bei `bandpilot_mode="manual"` — toggled jetzt
  (vorher No-Op).
- **T4** Sub-Toggle bei `_gain_measure_locked=True` blockt weiter (alle
  3 bp-Modi).
- **T5** Sub-Toggle bei `radio.ip=None` blockt weiter.
- **T6** OMNI/Auto-Hunt werden gestoppt vor Toggle (alle 3 bp-Modi).
- **T7** Bundle-G-Test der die alte „bp != off blockt"-Annahme prüft,
  wird auf neue Erwartung umgeschrieben (oder gelöscht falls direkt
  obsolet).

## 7. KISS-Bewertung

- **Code-Diff:** 2 Zeilen entfernen + Docstring kürzen (3 Zeilen).
- **Komplexität:** keine. Bandpilot ist bereits stateless, kein neuer
  Mechanismus nötig für „Override gilt bis Bandwechsel".
- **Risiko:** sehr klein. Side-Effect von Toggle bei bp=auto: Bandpilot
  hat zuvor einen Toast gezeigt mit „DX empfohlen". User toggled jetzt
  manuell zu Standard. Anzeige stimmt nicht mehr mit Toast überein —
  aber das ist Mike's expliziter Wunsch (Override).
