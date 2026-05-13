# P47 — Tote Frequenz-Settings + Statusbar-Filter-Anzeige entfernen (V1)

## Ziel

Zwei wirkungslose Frequenz-Settings (`audio_freq_hz` als TX-Default und
`max_decode_freq` als Decoder-Obergrenze) und die irreführende
Statusbar-Filter-Anzeige (`Filter: 100-3100 Hz`) ehrlich aus UI, Settings
und Anzeige entfernen. Defaults wandern als Konstanten in die Code-Pfade,
die sie heute aus den Settings lesen.

**Hintergrund (Konsens Mike + Claude + R1 13.05.2026):** Beide Settings
täuschen Steuerbarkeit vor, die nicht existiert:

- `audio_freq_hz` (TX Audio-Frequenz, Default 1500 Hz) wird nur als
  Startwert für `Encoder.__init__` genutzt — der CQ-Such-Algorithmus
  überschreibt `encoder.audio_freq_hz` dynamisch bei jedem Slot.
- `max_decode_freq` (Default 3000 Hz, UI-Range 1000–5000) wird nur einmal
  beim App-Start an `Decoder(max_freq=...)` gegeben. **`decoder.max_freq`
  wird nirgends im Code neu gesetzt** — auch nicht bei Modus-Wechsel
  (Code-Verifikation 13.05.: grep `\.max_freq\s*=` → genau 1 Treffer:
  `core/decoder.py:73` im Init). Eine User-Eingabe von 4000 wirkt also
  nur bis zum nächsten App-Neustart.
- Die Statusbar-Anzeige `_FILTERS = {"FT8":"100-3100", "FT4":"100-3100",
  "FT2":"100-4000"}` ist sogar **aktiv irreführend**: Für FT2 zeigt sie
  100–4000 Hz, der Decoder läuft aber faktisch auf 3000 Hz (Default
  bleibt unverändert beim Modus-Wechsel).

R1-Originalton: „Tote Settings sind toter Code und verletzen das Prinzip
der geringsten Überraschung."

## Akzeptanzkriterien

**AK1 — Settings-Keys entfernt.** `audio_freq_hz` und `max_decode_freq`
aus `DEFAULTS` und aus den `@property`-Wrappern in `config/settings.py`
entfernt. Alte JSON-Configs mit diesen Keys werden beim Laden
stillschweigend ignoriert (keine eigene Migrationslogik nötig — der
Settings-Loader nimmt nur DEFAULTS-Keys auf und schreibt beim Save nur
das, was im Code gesetzt wurde).

**AK2 — UI-Felder entfernt.** TX Audio-Frequenz-Spinbox und
Max. Decode-Frequenz-Spinbox aus `ui/settings_dialog.py` Tab „FT8" raus,
inkl. Form-Rows, Load/Save/Reset-Pfade und Hint-Strings (`tx_freq`,
`max_decode` aus dem Hint-Dict).

**AK3 — Statusbar-Filter-Anzeige raus.** `_FILTERS`-Dict und
`filter_str`-Berechnung aus `_update_statusbar()` in `ui/main_window.py`
entfernt, samt `Filter: ... Hz |`-Segment im zentralen `msg`-String.
Andere Statusbar-Bestandteile (Callsign, Locator, Modus+Band, Freq, DT,
AP, Antennen-Hint) bleiben unverändert in ihrer Reihenfolge.

**AK4 — Konstanten statt Settings-Lookup an den 2 betroffenen Init-Stellen.**

- `ui/main_window.py:144` `Encoder(settings.audio_freq_hz)` → `Encoder(1500)`
- `ui/main_window.py:145` `Decoder(max_freq=settings.max_decode_freq)`
  → `Decoder(max_freq=3000)`
- `config/settings.py:225` `get_normal_tx_freq` Fallback
  `self._data.get("audio_freq_hz", 1500)` → einfach `1500`

**AK5 — Tests grün.** Alle bestehenden Tests laufen weiter durch. Tests,
die diese Keys hart erwähnen (`tests/test_settings_dialog_smoke.py` Z.32-33,
61-62, 97), werden entsprechend angepasst (Keys aus Stub-Settings raus,
`expected_attrs` ohne `audio_freq` und `max_decode_freq`).

**AK6 — Keine Verhaltensänderung außerhalb dieser Streichungen.** Encoder
startet weiterhin auf 1500 Hz (CQ-Algorithmus überschreibt sowieso),
Decoder läuft weiter auf 3000 Hz max — also exakt das was heute
faktisch passiert. Statusbar zeigt jetzt einfach kein Filter-Segment
mehr.

## Betroffene Module/Dateien

| Datei | Zeile(n) | Was |
|---|---|---|
| `config/settings.py` | 60, 61 | DEFAULTS-Keys `audio_freq_hz`, `max_decode_freq` raus |
| `config/settings.py` | 170–171, 174–175 | Properties `audio_freq_hz`, `max_decode_freq` raus |
| `config/settings.py` | 225 | `get_normal_tx_freq` Fallback → hartes `1500` |
| `ui/settings_dialog.py` | 29, 30 | Hint-Strings `tx_freq`, `max_decode` raus |
| `ui/settings_dialog.py` | 285–293 | QSpinBox-Init `audio_freq`, `max_decode_freq` + Form-Rows raus |
| `ui/settings_dialog.py` | 506, 507 | Load-Pfad raus |
| `ui/settings_dialog.py` | 646, 647 | Save-Pfad raus |
| `ui/settings_dialog.py` | 693, 694 | Reset-Default-Pfad raus |
| `ui/main_window.py` | 144 | `Encoder(1500)` statt `Encoder(settings.audio_freq_hz)` |
| `ui/main_window.py` | 145 | `Decoder(max_freq=3000)` statt `Decoder(max_freq=settings.max_decode_freq)` |
| `ui/main_window.py` | 1108–1109 | `_FILTERS` + `filter_str` raus |
| `ui/main_window.py` | 1147 | `Filter: {filter_str} Hz | ` aus msg-String raus |
| `tests/test_settings_dialog_smoke.py` | 32–33, 61–62, 97 | Test-Stub-Settings + expected_attrs anpassen |

## Randbedingungen

- **KISS:** Keine Helper-Funktionen, keine Migrationsklasse. Direkt
  löschen, Konstanten hardcoden. Drei `1500` und ein `3000` sind besser
  als eine `DEFAULT_AUDIO_HZ`-Konstante mit einem Verweis.
- **Hardware-Pflicht ANT1=TX bleibt unberührt.** Kein TX-Pfad-Eingriff.
- **Hobby-Tool-Philosophie:** ehrliche UI > täuschende Eingabefelder.
- **Kein Bandwechsel-Schutz nötig** — der vorhandene Code-Pfad zeigt
  bereits, dass `decoder.max_freq` ohnehin nie geändert wird.
- **Tests müssen grün bleiben.** `Encoder`-Default-Wert in `core/encoder.py`
  (1000) bleibt — der wird nur in 8 Test-Helpern explizit auf 1500
  gesetzt; das bleibt so. Nur der App-Pfad ändert sich.

## Nicht im Scope

- `audio_freq_hz_for_band` / `get_normal_tx_freq` als Konzept bleibt
  (per-Band-TX-Frequenz für Normal-Modus) — nur der Fallback in Z.225
  wird konstant.
- Encoder-Klasse Default-Wert (`audio_freq_hz: int = 1000` in
  `core/encoder.py:49`) bleibt unverändert.
- Decoder-Klasse Default-Wert (`max_freq: int = 3000` in
  `core/decoder.py:70`) bleibt unverändert.
- Keine neuen Einstellungen, kein UI-Redesign vom FT8-Tab — nur die 2
  Form-Rows raus.
- AP-Lite, OMNI-CQ, Diversity, CQ-Algorithmus: alles bleibt unberührt.
- TUNE_FREQS und Per-Band-Frequenzen: nicht angefasst.

## Testbarkeit

- **T1 — Settings-Smoke ohne tote Keys:** Settings-Stub ohne
  `audio_freq_hz`/`max_decode_freq` lädt, Dialog erzeugt sich,
  hat die beiden Widget-Attribute NICHT.
- **T2 — Statusbar ohne Filter-Segment:** `_update_statusbar` aufrufen
  und assertieren dass `"Filter:"` nicht im `statusBar().currentMessage()`
  steht.
- **T3 — Settings-Migration silent:** alte JSON mit Keys
  `audio_freq_hz=1234` + `max_decode_freq=4500` laden — Settings-Objekt
  hat diese Werte NICHT als Attribute, kein AttributeError beim Save.
- **T4 — Encoder/Decoder-Init:** Smoke-Test dass `main_window` ohne
  diese Settings-Keys startet (`Encoder(1500)` + `Decoder(max_freq=3000)`).

Erwartung: ~3 neue Tests, ~3-5 Tests angepasst, Suite-Größe 1162 → ~1165.

## Geplante Commit-Reihenfolge (atomar)

1. `config/settings.py` — DEFAULTS + Properties + `get_normal_tx_freq`-Fallback
2. `ui/settings_dialog.py` — Hints + UI-Felder + Load/Save/Reset
3. `ui/main_window.py` — Encoder/Decoder-Init + Statusbar-Filter
4. `tests/test_settings_dialog_smoke.py` — Stub + expected_attrs anpassen
5. Neue P47-Tests `tests/test_p47_dead_freq_settings.py`
6. APP_VERSION 0.97.10 → 0.97.11 + HISTORY.md + HANDOFF.md + Doku

## Risiko

**LOW.** Beide Settings sind faktisch wirkungslos (CQ-Algo überschreibt
TX-Freq, Decoder-Max wird nie geändert). Statusbar-Anzeige war
irreführend, ihre Entfernung macht das Tool ehrlicher. Keine bestehende
Diversity-/CQ-/QSO-/OMNI-Logik wird berührt.
