# R1 — P129 P128-Filter 73/RR73 als Whitelist durchlassen

## Was ich will

Reviewer. KEIN Code. Severity-Findings. KISS-Bewertung. Code ist Referenz.

## Kontext

**Mike-Field-Beobachtung 25.05.2026 ~13:24 (Screenshot 3 QSOs):**
M1DBW, 5B4AMX, G0CLT — 3 QSOs hintereinander, ALLE ohne 73-Empfang
im Log. Statistisch ungewöhnlich (FT8: viele Stationen senden 73 als
Bestätigung).

**Mike-Hypothese:** „kann das sein das wir die meldung blocken?"

**Root Cause (V2-verifiziert):** P128 (v0.98.07, gleiche Session,
heute) setzt 60s-Cooldown nach `qso_complete.emit` → blockt ALLE
weiteren Empf.-Einträge im Fenster. Auch positive 73-Bestätigungen.

**Timing-Beispiel M1DBW:**
- 13:24:15: Mike sendet RR73 → `qso_complete.emit` → Cooldown gesetzt
- 13:24:30 (Even-Slot): M1DBW könnte 73 senden
- 13:24:42 (Decoder fertig): 27s nach Cooldown-Start → BLOCKIERT

User sieht nie ob die Gegenstation das QSO sauber abgeschlossen hat.

## Mike-Spec war:

> „beendet ist beendet" — gegen WIEDERHOLTE R-Reports/Grids
> (Endlos-Spam-Vektor)

**P128 wurde zu breit:** Mike wollte Spam blocken, nicht
Bestätigungen.

## V1/V2-Architektur (KISS)

**Eine atomare Änderung in `_p128_recently_completed_block`** (mw_cycle.py:864):

Bisher:
```python
def _p128_recently_completed_block(self, caller: str) -> bool:
    store = getattr(self, '_recently_completed_qsos', None)
    if not store:
        return False
    completion_ts = store.get(caller)
    if completion_ts is None:
        return False
    if time.monotonic() - completion_ts < _RECENTLY_COMPLETED_BLOCK_S:
        return True
    del store[caller]
    return False
```

**P129 Neu:** Funktion bekommt `msg` als 2. Param. Im Block-Check
wird `msg.is_73` und `msg.is_rr73` durchgelassen:

```python
def _p128_recently_completed_block(self, caller: str, msg: FT8Message = None) -> bool:
    # P129: Bestätigungen IMMER durchlassen (auch im Cooldown)
    if msg is not None and (msg.is_73 or msg.is_rr73):
        return False
    # ... Rest unverändert
```

Call-Site Anpassung in `on_message_decoded` Z. 797:
```python
if not self._p128_recently_completed_block(msg.caller, msg):  # +msg
```

**Mike-Effekt:**
- 73-Bestätigung von Gegenstation nach unserem RR73 → erscheint im Log ✓
- Wiederholte R-Reports/Grids im 60s-Fenster → weiterhin geblockt ✓
- Verhalten wie ursprünglich von Mike intendiert (Spam-Block, kein
  Bestätigungs-Block)

## ACs

- **AC1:** `is_73`-Messages werden im Cooldown-Fenster durchgelassen
  (kein Block)
- **AC2:** `is_rr73`-Messages auch durchgelassen (selbe Klasse,
  Bestätigungs-Charakter)
- **AC3:** R-Reports im Cooldown-Fenster bleiben geblockt (KEINE
  Regression der ursprünglichen P128-Funktion)
- **AC4:** Grid-Messages im Cooldown-Fenster bleiben geblockt
- **AC5:** Plain Reports im Cooldown-Fenster bleiben geblockt
- **AC6:** Optionaler `msg`-Param (Default None) erhält Backward-Compat
  für Test-Fakes ohne msg-Objekt
- **AC7:** Wenn `msg = None` → Verhalten wie bisher (nur Caller-Check)

## Risiken

- **R1** 🟢: API-Erweiterung (Optional-Param) bricht keine bestehenden
  Tests. Defensive `if msg is not None and ...`.
- **R2** 🟡: Could-be-better: könnte auch Mike-Spec sein dass NUR `73`
  durchgelassen wird (RR73 wäre eher unüblich nach unserem RR73 — die
  Gegenstation würde dann ja sofort ihr 73 senden, nicht ein weiteres
  RR73). Aber Whitelist breiter macht semantisch Sinn.
- **R3** 🟢: Test-Aufwand: 3-4 neue Tests (Whitelist-Pfad), 1
  bestehender Test (T2 Helper) bleibt grün (msg=None Default).

## Was du prüfen sollst

**Frage 1 (KISS-Bewertung):**
1-Zeilen-Whitelist im Filter, Optional-Param mit Backward-Compat.
Sauberste denkbare Lösung oder gibt's KISS-ere Alternative?

**Frage 2 (Whitelist-Scope):**
`is_73` || `is_rr73` — sind das ALLE Bestätigungs-Typen die durchgelassen
werden sollen? Was ist mit `is_r_report` (R+SNR)? Argument PRO:
„R" ist auch eine Bestätigung. Argument CONTRA: P100-Pattern hat
gezeigt dass R-Reports im WAIT_RR73-Pfad als RR73-Vorgänger fungieren
können — könnten zu Re-Trigger führen wenn State-Machine nicht
korrekt im IDLE/TIMEOUT ist.

Mike-Spec ist offen — was empfiehlst du?

**Frage 3 (Timing-Verifikation):**
Bei Mike's Screenshot (3 QSOs hintereinander, alle ohne 73): mein
Verständnis ist, dass `qso_complete.emit` direkt nach RR73-Send läuft
(TX_RR73 → on_message_sent → qso_complete). 73 von Gegenstation
kommt im NÄCHSTEN Slot (15s später). Decoder-Latenz ~3s. Total:
~18-30s nach Cooldown-Start → fällt in 60s-Fenster → wird geblockt.

Korrekt analysiert?

**Frage 4 (Race-Conditions):**
Optional-Param-Erweiterung in Mixin-Methode. Kein Thread-Safety-
Problem (alles GUI-Thread). Pattern in anderen Methoden auch
verwendbar?

**Frage 5 (Edge-Case 73 von ANDERER Station):**
Was wenn EA1FLB ein 73 sendet während wir im 60s-Cooldown von M1DBW
sind? Whitelist greift NUR wenn caller im Cooldown ist (`store.get(caller)`
muss truthy sein). EA1FLB ist nicht im store → kein Cooldown-Block →
73 wird normal angezeigt. Korrekt?

**Frage 6 (Tests-Vollständigkeit):**
Vorschlag:
- T1: 73-Message von Cooldown-Caller → durchgelassen
- T2: RR73-Message von Cooldown-Caller → durchgelassen
- T3: R-Report von Cooldown-Caller → weiter geblockt
- T4: Plain Report → weiter geblockt
- T5: msg=None Default → Verhalten wie bisher
- T6: 73 von anderem Caller (nicht im Cooldown) → durchgelassen

Was fehlt?

## Verdict erwartet

GO/NACHBESSERN. KISS-Bewertung.
