# OPT-62 (K2) Scope-Entscheidung — 3 Preset-Zugriffe in config/settings.py

## Kontext
Autonome **Optimierungs-Kampagne**: NUR Optimierung, **keine Verhaltensänderung**,
KISS. **Breaking Changes an öffentlichen Schnittstellen (Settings-JSON-Format) →
Mike vorlegen** (Projektregel). Ich brauche deine ehrliche Einschätzung, ob hier
ein risikoarmer KISS-Gewinn drin ist ODER ob OPT-62 durch eine frühere
Architektur-Migration obsolet ist (dann herabstufen wie wir OPT-60 herabgestuft
haben — kein Busy-Work an totem Code).

## Verifizierter IST-Zustand (von mir gegen Live-Code geprüft)
Der Audit-Befund K2 lautete: „3 fast gleiche Preset-Zugriffe
(`get_dx_preset`/`get_gain_preset`/`get_normal_preset`) verwirren →
vereinheitlichen". **ABER der Befund ist veraltet:**
- `get_normal_preset` wurde bereits entfernt (Bundle A / OPT-43, deprecated-Stub).
- Die App nutzt für Gain-Presets seit P80/P51 (v0.97.5x) den unified
  `core/preset_store.py` (`PresetStore.save_gain`) bzw. `rf_preset_store.py`,
  NICHT mehr diese settings-Methoden.

**Aktuelle Verwendung (grep, ohne venv/Appsicherungen):**
- `get_dx_preset` — **nur in `tests/test_modules.py`** (App: 0 Refs).
- `get_gain_preset` — **nur in `tests/test_modules.py`** (App: 0 Refs).
- `save_dx_preset` — **tote API**; `tests/test_p51` T7 prüft EXPLIZIT, dass sie
  NICHT mehr gerufen wird (Regression-Wächter gegen Rückfall auf alte Persistenz).
- `save_normal_preset` — **no-op DEPRECATED** (nur `print`); `tests/test_p80`
  prüft den no-op-Status; mw_radio:2187 „keine separate save_normal_preset-
  Persistenz mehr".

**Äquivalenz (Reader):** `get_dx_preset(band, mode=X)` ≡
`get_gain_preset(band, mode="standard", ft_mode=X)` — beide lesen
`dx_presets[f"{band}_{X}"]` → `dx_presets[band]`. `get_gain_preset` mit
`mode="dx"` liest zusätzlich `dx_gain_presets`. → `get_dx_preset` ist ein
exakter Spezialfall von `get_gain_preset`.

(Die echten Methoden-Bodies stecken in der angehängten settings.py, Z.340-407.)

## Optionen
- **A** — `get_dx_preset` → dünner Wrapper auf `get_gain_preset` (DRY-Konsolidierung
  der zwei fast identischen Reader). Aber: beide sind test-only → App-Nutzen ~0,
  nur Test-Lesbarkeit.
- **B** — `save_dx_preset` + `save_normal_preset` (tot/no-op) entfernen + ihre
  Tests. ABER: berührt öffentliche API + entfernt bewusste Regression-Wächter →
  m.E. Mike-Sache (Breaking Change), nicht autonom.
- **C** — OPT-62 **herabstufen/obsolet** (analog OPT-60): Befund durch P80/P51-
  Migration + Bundle A überholt; verbleibende Methoden sind bewusst gehaltene
  deprecated/test-only-API (Audit Z.98 empfahl selbst „behalten — kein
  Handlungsbedarf"). Eine Vereinheitlichung von test-only-Code ist Busy-Work
  ohne App-Gewinn; Entfernen ist API-Entscheidung → Mike.
- **D** — Kombination / etwas, das ich übersehe.

## Meine Tendenz
**C** mit optionalem kleinen **A** (get_dx_preset als Wrapper, falls du echten
Lesbarkeitswert sicht). Die save_*-Entfernung (B) lege ich Mike vor statt
autonom zu machen.

## Fragen
1. Stimmst du zu, dass OPT-62 (K2) durch die Architektur-Migration größtenteils
   obsolet ist und KEIN systematischer KISS-Gewinn für die App mehr drinsteckt?
2. Lohnt A (get_dx_preset → Wrapper) als Mini-Dedup, oder ist das Overengineering
   an test-only-Code (KISS sagt: nicht anfassen was nur Tests nutzen)?
3. Ist B (save_* entfernen) wirklich Mike-Sache (öffentliche API + Regression-
   Wächter), oder so eindeutig tot, dass es als Stufe-1-Tote-Code-Entfernung
   autonom OK wäre?
4. Übersehe ich eine echte, risikoarme KISS-Vereinfachung?

Knapp + konkret. Code ist Referenz.
