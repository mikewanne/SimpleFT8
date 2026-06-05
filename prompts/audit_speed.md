# Optimierungs-Audit (1/2): GESCHWINDIGKEIT — Pro-Slot-Hot-Path

## Kontext
SimpleFT8 = Hobby-FT8/FT4-Tool (PySide6, FlexRadio, macOS, älterer iMac 2015).
**Ziel dieser Analyse: Geschwindigkeit + Vereinfachung im Hot-Path.** KEIN Code
ändern — nur Befund + konkrete Vorschläge mit Aufwand/Risiko.

**Hot-Path-Fakten:**
- Der Decoder läuft 1×/Slot (FT8 15 s, FT4 7,5 s, FT2 3,8 s) im eigenen Thread.
- `_on_meter_update` (FWDPWR/SWR) feuert **sehr häufig** (VITA-49-Meter-Push, viele
  Male/s) — hier darf NICHTS Teures rein (schon mal 4-GB-Logflut-Falle gehabt).
- Diversity schaltet pro Zyklus die RX-Antenne, Histogramm unter Lock.
- App soll auf dem 2015er-iMac „flüssig" bleiben (Mike-Wunsch).

**Bekannte RESERVIERTE Stellen — NICHT als tot/entfernbar vorschlagen:**
Slice-B-Code in flexradio (`enable_diversity`/`disable_diversity`/`_build_vita49_packet`/
`_create_stream`/`_cleanup_extra_slices`/`dx_reset`/`set_preamp`) = Multiband-Reserve.
ft8_lib = vendored C, nicht anfassen.

## Frage
Schau in die angehängten Hot-Path-Dateien und finde **konkrete** Geschwindigkeits-
und Vereinfachungs-Chancen:
1. Unnötige Arbeit pro Slot/pro Meter-Tick (Allokationen in Schleifen, wiederholte
   Konvertierungen, np-Kopien, Re-Compiles von Regex, String-Formatierung die immer
   läuft, Locks die zu breit greifen).
2. Stellen wo numpy-Vektorisierung statt Python-Schleife geht.
3. Redundante Neuberechnung (Werte die sich pro Slot nicht ändern, aber jedes Mal
   neu berechnet werden → cachebar).
4. Über-komplizierte Logik die einfacher (KISS) ginge ohne Verhaltensänderung.

Pro Fund: **Datei:Zeile, was, warum langsam/komplex, konkreter Fix, Aufwand (S/M/L),
Risiko (niedrig/mittel/hoch)**. Code-Pfade gegen die angehängten Dateien prüfen, nicht
raten. Priorisiere nach Wirkung/Aufwand. Knapp und konkret.
