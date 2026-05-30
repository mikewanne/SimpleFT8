# HANDOFF — SimpleFT8

**Aktueller Stand:** v0.98.47 (30.05.2026) — P162 zurückgenommen, **kein Bug**.
Tests 2205 grün. `core/qso_state.py` unberührt.

---

## Letzte Session (30.05.2026)

**P162 war eine Fehldiagnose — der Code war die ganze Zeit korrekt (Mike-Klärung).**

Screenshot 10:56–10:59: Wir riefen von Hand EG5SUN (`→ EG5SUN DA1MHH -25`).
ZEITGLEICH rief uns eine völlig andere Station blind auf Verdacht
(`← DA1MHH YO60GW R-12`). Die App reagierte korrekt NICHT auf YO60GW
(≠ QSO-Partner EG5SUN); EG5SUN antwortete nie → Timeout. Regelkonform.
Das vermeintliche U+2212-Minus existierte nie (kein U+2212 in den Logs).

**Entfernt (Revert):** `core/message.py:is_report` Original,
`tests/test_p162_unicode_report.py` gelöscht, main.py 0.98.46→0.98.47,
HISTORY/CLAUDE korrigiert. Kein TODO-Bug-Eintrag (Mike: kein Eintrag nötig).

**NOCH NICHT GEPUSHT** — v0.98.46 (mit der Falschbehauptung „GELÖST") ist bereits
auf GitHub (origin = e6426ec). Push des Reverts braucht Mike-Freigabe.

---

## ⚠ Tooling-Warnung
Bash/Read-Ausgaben werden zeitweise stark trunkiert/verzögert. Dateien selbst sind
korrekt; verlässlich nur Schreiben via Python + Verifikation über kurze Counts +
pytest-Returncode.
