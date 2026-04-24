#!/usr/bin/env python3
"""SimpleFT8 Auswertungs-Script — PNG-Diagramme aus statistics/ Markdown-Dateien.

Aufruf: python3 scripts/generate_plots.py
Output: auswertung/stationen_<band>_<proto>.png          (DE)
        auswertung/en/stationen_<band>_<proto>.png        (EN)
        auswertung/diversity_<band>_<proto>.png           (DE)
        auswertung/en/diversity_<band>_<proto>.png        (EN)
        auswertung/SimpleFT8_Bericht.pdf                  (DE)
        auswertung/en/SimpleFT8_Report.pdf                (EN)

X-Achse: Stunde des Tages (00–23 UTC), gemittelt über alle Messtage.
Konfidenzband: Min–Max der Tages-Mittelwerte (Tag-zu-Tag-Variabilität).
"""

import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.colors as mc
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

BASE_DIR = Path(__file__).parent.parent
STATS_DIR = BASE_DIR / "statistics"
OUTPUT_DIR = BASE_DIR / "auswertung"
OUTPUT_DIR_EN = BASE_DIR / "auswertung" / "en"

# Language → output directory mapping
LANG_DIR = {"de": OUTPUT_DIR, "en": OUTPUT_DIR_EN}

RX_MODES = ["Normal", "Diversity_Normal", "Diversity_Dx"]

DARK_BG = "#1e1e1e"
DARK_FG = "#d4d4d4"
DARK_GRID = "#333333"

COLORS = {
    "Normal":           "#b0b0b0",  # helles Grau — Baseline (neutraler, hebt sich ab)
    "Diversity_Normal": "#5d8fd9",  # gesättigtes Blau — Standard (kühle Energie)
    "Diversity_Dx":     "#f0a050",  # warm Orange — DX (Tableau-bewährt, unverändert)
    "rescue":           "#4cda7a",  # kühles Grün — Rescue Cap (kontrastiert zu Blau+Orange)
}

# Dunklere Varianten für gestrichelte Rescue-Linien im Stationen-Diagramm
COLORS_RESCUE = {
    "Diversity_Normal": "#3a6098",  # 30% dunkler als #5d8fd9
    "Diversity_Dx":     "#a07030",  # 30% dunkler als #f0a050
}

_COL_MAP = {
    "zeit": "zeit",
    "stationen": "stationen",
    "ø snr": "avg_snr",
    "ant2 wins": "ant2_wins",
    "ø δsnr": "avg_delta_snr",
    "call": "call",
    "ant1 db": "ant1_db",
    "ant2 db": "ant2_db",
    "δ db": "delta_db",
    "gewinner": "gewinner",
    "saved": "saved",
}

# ── Lokalisierungs-Texte / Localisation strings ───────────────────────────────

TEXTS = {
    "de": {
        # Achsenbeschriftungen / Axis labels
        "x_label":          "Stunde (UTC)",
        "y_label_line":     "Ø Stationen / 15s-Zyklus",
        "y_label_bar":      "Ø Stationen pro 15s-Zyklus",

        # Diagramm-Titel / Chart titles
        "title_stations":   "Empfangene Stationen — {band} {protocol}",
        "title_diversity":  "Empfang im Vergleich — {band} {protocol}",

        # Basis-Label (Legende) / Basis label (legend)
        "basis_entry":      "{label}\n{n_d} Tag{pl} · {n_c_fmt} Messpunkte",
        "day_plural_1":     "",       # Singular-Suffix: "1 Tag" (kein Suffix)
        "day_plural_n":     "e",      # Plural-Suffix:   "2 Tage"
        "thousands_sep":    ".",      # Tausender-Trennzeichen DE: 6.585

        # Modusbezeichnungen / Mode labels
        "mode_labels": {
            "Normal":           "Normal (1 Antenne)",
            "Diversity_Normal": "Diversity Standard",
            "Diversity_Dx":     "Diversity DX",
        },

        # Rescue-Legende
        "rescue_legend":    "davon gerettet (ANT1 unter −24 dB)",
        "rescue_line":      "+ Rescue Stationen",

        # Erklärungs-Fußzeile Stationen-Diagramm
        "expl_stations": (
            "Normal (grau): 1 Antenne, wie WSJT-X — Vergleichsbasis.\n"
            "Diversity Standard (blau): 2 Antennen, wählt automatisch die mit mehr Stationen.\n"
            "Diversity DX (orange): 2 Antennen, wählt die mit mehr schwachen DX-Signalen.\n"
            "Schattiertes Band: Schwankung zwischen Messtagen — Linie = Mittelwert.\n"
            "Rescue Stationen (gestrichelt): Von ANT1 unter −24 dB empfangen — ANT2 hebt das Signal über die Dekodiergrenze.\n"
            "Mehr Stationen = Band offen (Ionosphäre reflektiert Signale aus aller Welt). "
            "Diversity = System wählt automatisch die bessere Antenne."
        ),

        # Erklärungs-Fußzeile Diversity-Diagramm (Platzhalter {band} und {protocol})
        "expl_diversity": (
            "Normal (grau): 1 Antenne, wie WSJT-X — dient als Vergleichsbasis.\n"
            "Diversity Standard (blau): 2 Antennen — wählt automatisch die Antenne, die mehr Stationen empfängt.\n"
            "Diversity DX (orange): 2 Antennen — wählt die Antenne mit mehr schwachen DX-Signalen (SNR unter −10 dB).\n"
            "Fehlerbalken (weiße Striche): Schwankung zwischen Messtagen — je mehr Tage, desto stabiler der Wert.\n"
            "Grüne Kappe (+N): Stationen, die ANT1 allein nicht dekodieren konnte — ANT2 hat sie gerettet (Signal unter −24 dB).\n"
            "\n"
            "Rohdaten: statistics/{{Modus}}/{band}/{protocol}/  ·  github.com/mikewanne/SimpleFT8"
        ),

        # Zeitbereich / Time range
        "no_data":  "keine Daten",
        "date_to":  "bis",

        # PDF Footer
        "footer_left": "SimpleFT8 Diversity Feldstudie — DA1MHH / Mike Hammerer  ·  {gen_date}",

        # Seitenzahl-Label / Page number label
        "page":     "Seite {n}",

        # PDF Name
        "pdf_name": "SimpleFT8_Bericht.pdf",

        # ── Titelseite (S.1) ────────────────────────────────────────────────
        "p1_title":    "SimpleFT8 — Zwei Antennen, ein Vergleich",
        "p1_subtitle": "Was bringt Diversity wirklich? — 40m FT8, erste Messergebnisse",
        "p1_period_label": "Zeitraum: {time_range}   ·   Ausgewertete 15s-Zyklen: {total_cyc}",
        "p1_summary_title": "Kurz zusammengefasst:",
        "p1_summary_body": (
            "Mit Diversity Standard (blau) habe ich im Schnitt {s_gain} mehr Stationen dekodiert als mit einer einzelnen Antenne.\n"
            "Zählt man die 'geretteten' Stationen dazu, kommt man auf bis zu {s_gain_r}.\n"
            "Diversity DX (orange) bringt {d_gain} — weniger als Standard, aber gezielter auf schwache DX-Signale."
        ),
        "p1_caveat": (
            "Wichtig: Das sind erst 2 Messtage, nur Morgenstunden (05–12 Uhr UTC). "
            "Die Zahlen können sich noch verschieben — aber der Trend ist klar erkennbar."
        ),
        "p1_modes_title": "Was bedeuten die drei Modi?",
        "p1_modes_body": (
            "Normal (grau): Eine Antenne, keine besondere Logik — so wie WSJT-X. Das ist die Vergleichsbasis.\n"
            "Diversity Standard (blau): Zwei Antennen. Das System wählt automatisch die Antenne mit mehr Stationen.\n"
            "Diversity DX (orange): Zwei Antennen. Wählt die Antenne mit den schwächsten DX-Signalen (unter −10 dB).\n"
            "Rescue (grüne Kappen): Stationen die ANT1 nicht hören konnte — ANT2 hat sie trotzdem dekodiert."
        ),

        # ── Methodik-Seite (S.2) ────────────────────────────────────────────
        "p2_header_title":    "Wie wurde gemessen?",
        "p2_header_subtitle": "Setup, Zeitraum und ein bisschen Hintergrund",
        "p2_setup_title": "Das Setup",
        "p2_setup_body": (
            "Gemessen auf 40m FT8 mit dem FlexRadio FLEX-8400M — zwei Antennenanschlüsse, gleiche Frequenz.\n"
            "Zeitraum: {time_range}, jeweils morgens zwischen 05:00 und 12:00 UTC. Ja, die Nacht fehlt noch — kommt noch.\n"
            "Zyklen ausgewertet: Normal {n_c} ({n_d} Tag/e)  |  Diversity Standard {s_c} ({s_d} Tag/e)  |  Diversity DX {d_c} ({d_d} Tag/e).\n"
            "Jeder FT8-Zyklus dauert 15 Sekunden — die App zählt pro Zyklus wie viele Stationen dekodiert wurden."
        ),
        "p2_pooled_title": "Warum nicht einfach den Tagesdurchschnitt nehmen?",
        "p2_pooled_body": (
            "Gute Frage — ich hatte das auch erst so. Aber wenn an einem Tag nur 20 Zyklen gemessen wurden\n"
            "und an einem anderen 500, dann würde der kurze Tag genauso stark ins Ergebnis eingehen wie der lange.\n"
            "Das wäre unfair. Deswegen werden alle Einzelwerte direkt zusammengezählt und gemittelt — egal von welchem Tag.\n"
            "Das ergibt ein Bild das näher an der Realität liegt."
        ),
        "p2_rescue_title": "Was sind 'gerettete Stationen' (Rescue)?",
        "p2_rescue_body": (
            "Stell dir vor eine Station sendet so schwach dass ANT1 das Signal unter −24 dB empfängt.\n"
            "Das ist bei FT8 die Grenze — darunter kann man praktisch nicht mehr dekodieren.\n"
            "ANT2 empfängt dieselbe Station aber mit etwas mehr Pegel — und dekodiert sie trotzdem.\n"
            "Das nennen wir 'Rescue'. Die grünen Kappen in den Diagrammen zeigen genau diese Stationen.\n"
            "Ob man die mitzählt oder lieber separat betrachtet — das ist Ansichtssache. Beide Werte stehen im Bericht."
        ),
        "p2_rawdata_title": "Wo kommen die Rohdaten her?",
        "p2_rawdata_body": (
            "SimpleFT8 schreibt pro Stunde eine kleine Markdown-Datei mit allen Zykluswerten.\n"
            "Kein vorberechneter Durchschnitt — nur Rohdaten. Das Auswertungs-Script rechnet alles frisch durch.\n"
            "Wer nachschauen will: statistics/ im GitHub-Repo, alles offen."
        ),

        # ── Ergebnisse-Seite (S.3) ──────────────────────────────────────────
        "p3_header_title":    "Hauptergebnisse — Vergleichstabelle",
        "p3_header_subtitle": "40m FT8 · Pooled Mean",
        "p3_col_labels": [
            "Modus", "Ø Stat.\n/Zyklus", "vs Normal\nohne Rescue",
            "vs Normal\n+ Rescue", "Rescue\nallein", "Messtage", "Zyklen",
        ],
        "p3_note1": (
            "Ø Stat./Zyklus = Mittelwert über alle Einzelzyklen direkt (nicht erst Tagesdurchschnitt).   "
            "Rescue = ANT1 unter −24 dB, ANT2 hat trotzdem dekodiert."
        ),
        "p3_note2": (
            "Noch erst 2 Messtage, nur Morgenstunden 05–12 Uhr UTC — Nacht und Abend fehlen noch. "
            "Die Zahlen können sich mit mehr Daten noch etwas verschieben."
        ),

        # ── Diagramm-Seite Stationen (S.4) ──────────────────────────────────
        "p4_title":      "Stationen pro Stunde — alle drei Modi im Vergleich",
        "p4_subtitle":   "{band} {protocol} — Linie = Mittelwert, schattiertes Band = Schwankung zwischen den Messtagen",
        "p4_annotation": (
            "Man sieht gut wie die graue Linie (Normal, eine Antenne) fast immer unter blau und orange liegt. "
            "Das schattierte Band zeigt die Schwankung zwischen den beiden Messtagen — je mehr Tage dazukommen, desto enger wird das."
        ),

        # ── Diagramm-Seite Diversity (S.5) ──────────────────────────────────
        "p5_title":      "Direktvergleich — Balken pro Stunde, drei Modi nebeneinander",
        "p5_subtitle":   "{band} {protocol} — Normal (grau) | Diversity Standard (blau) | Diversity DX (orange) | Rescue-Kappen (grün)",
        "p5_annotation": (
            "Die grünen Kappen (+N) oben auf den Balken zeigen Stationen die ANT1 nicht dekodieren konnte — "
            "Signal unter −24 dB. ANT2 hat sie trotzdem gerettet. Ob man die mitzählt oder nicht — Ansichtssache. "
            "Weiße Fehlerbalken zeigen die Schwankung zwischen den Messtagen."
        ),

        # ── Rescue-Seite (S.6) ──────────────────────────────────────────────
        "p6_header_title":    "Die grünen Kappen — zählen oder nicht?",
        "p6_header_subtitle": "Rescue-Stationen: Was steckt dahinter und was sagen sie aus?",
        "p6_about_title": "Worum geht's?",
        "p6_about_body": (
            "Im Diversity-Diagramm sieht man oben auf manchen Balken kleine grüne Kappen mit einem +N davor.\n"
            "Das sind Stationen die ANT1 nicht dekodieren konnte — deren Signal war unter −24 dB, also zu schwach.\n"
            "ANT2 hat sie trotzdem gehört und dekodiert. Im Messzeitraum waren das im Schnitt\n"
            "Ø {s_rsc:.1f} Stationen pro Stunde bei Diversity Standard, und Ø {d_rsc:.1f}/h bei Diversity DX."
        ),
        "p6_pro_title": "Warum spricht was dafür, sie mitzuzählen?",
        "p6_pro_body": (
            "Weil das QSO für den Operator real ist — egal ob ANT1 oder ANT2 es ermöglicht hat.\n"
            "Diese Stationen wären mit einer einzelnen Antenne gar nicht im Log gelandet.\n"
            "Das ist kein Messartefakt — das ist genau der Punkt warum man eine zweite Antenne betreibt.\n"
            "Mit Rescue: Standard {s_gain_r}, DX {d_gain_r} — das ist das Gesamtbild."
        ),
        "p6_con_title": "Warum kann man sie auch weglassen?",
        "p6_con_body": (
            "SNR-Werte schwanken innerhalb der 15 Sekunden eines Zyklus — eine Station die gerade\n"
            "unter −24 dB liegt könnte beim nächsten Zyklus schon drüber sein.\n"
            "Die −24 dB-Grenze ist ein Erfahrungswert, kein Naturgesetz.\n"
            "Wer einen sauberen Vergleich mit anderen Systemen machen will, "
            "zählt lieber nur was ANT1 direkt dekodiert."
        ),
        "p6_closing": (
            "Deswegen stehen in diesem Bericht immer beide Zahlen: einmal ohne Rescue (der konservative Wert)\n"
            "und einmal mit Rescue (das was im echten Betrieb rauskommt). Jeder kann sich das raussuchen was ihm passt."
        ),

        # ── Fazit-Seite (S.7) ───────────────────────────────────────────────
        "p7_header_title":    "Was kann man daraus mitnehmen?",
        "p7_header_subtitle": "Fazit und was als nächstes gemessen wird",
        "p7_visible_title": "Was man klar sehen kann:",
        "p7_fazit_body": (
            "Diversity Standard bringt über beide Messtage konsistent zwischen "
            "{gain_lo:.0f}% und {gain_hi:.0f}% mehr Stationen — "
            "je nachdem ob man\ndie geretteten mitzählt oder nicht. Das ist kein Zufall, das wiederholt sich.\n"
            "Diversity DX liegt bei {d_gain:.0f}% ohne Rescue — weniger als Standard, "
            "aber DX optimiert bewusst\nauf die schwächsten Signale. Wer viel DX macht, für den macht das Sinn."
        ),
        "p7_fazit_best": (
            "\nDer stärkste Effekt war um {hour:02d}:00 UTC mit +{s_gain:.0f}% — "
            "das ist typisch die Zeit wo das Band gerade aufmacht oder zumacht."
        ),
        "p7_cannot_title": "Was man noch nicht sagen kann:",
        "p7_cannot_body": (
            "Erst 2 Messtage — das reicht um einen Trend zu sehen, aber nicht um belastbare Aussagen zu machen.\n"
            "Die Nacht und die Abendstunden fehlen komplett — auf 40m ist es abends oft deutlich besser.\n"
            "Contest-Betrieb, Geo-Sturm, schlechte Bedingungen — das wurde noch nicht getestet.\n"
            "Ob das auf anderen Transceivern genauso funktioniert — keine Ahnung, bisher nur auf dem FLEX."
        ),
        "p7_next_title": "Was kommt als nächstes:",
        "p7_next_body": (
            "Nacht- und Abendmessungen auf 40m — das ist der interessante Teil den ich noch nicht habe.\n"
            "Mehr Tage damit die Balken im Diagramm stabiler werden und die Schwankungen kleiner.\n"
            "20m kommt irgendwann auch — aber erst wenn genug Daten da sind. Nicht vorher.\n"
            "Dieser Bericht aktualisiert sich automatisch sobald neue Daten reinkommen."
        ),
        "p7_raw_link": (
            "Wer in die Rohdaten schauen will: statistics/  im Repo  ·  github.com/mikewanne/SimpleFT8  ·  DA1MHH"
        ),
    },

    "en": {
        # Achsenbeschriftungen / Axis labels
        "x_label":          "Hour (UTC)",
        "y_label_line":     "Avg. Stations / 15s Cycle",
        "y_label_bar":      "Avg. Stations per 15s Cycle",

        # Diagramm-Titel / Chart titles
        "title_stations":   "Decoded Stations — {band} {protocol}",
        "title_diversity":  "Reception Comparison — {band} {protocol}",

        # Basis-Label (Legende) / Basis label (legend)
        "basis_entry":      "{label}\n{n_d} day{pl} · {n_c_fmt} data points",
        "day_plural_1":     "",    # singular suffix: "1 day" (no suffix)
        "day_plural_n":     "s",   # plural suffix:   "2 days"
        "thousands_sep":    ",",   # thousands separator EN: 6,585

        # Modusbezeichnungen / Mode labels
        "mode_labels": {
            "Normal":           "Normal (1 Antenna)",
            "Diversity_Normal": "Diversity Standard",
            "Diversity_Dx":     "Diversity DX",
        },

        # Rescue-Legende
        "rescue_legend":    "rescued (ANT1 below −24 dB)",
        "rescue_line":      "+ Rescue Stations",

        # Erklärungs-Fußzeile Stationen-Diagramm
        "expl_stations": (
            "Normal (grey): 1 antenna, like WSJT-X — baseline reference.\n"
            "Diversity Standard (blue): 2 antennas, automatically selects the one with more decoded stations.\n"
            "Diversity DX (orange): 2 antennas, selects the one with more weak DX signals.\n"
            "Shaded band: Day-to-day variation — line = mean value.\n"
            "Rescue Stations (dashed): Received by ANT1 below −24 dB — ANT2 boosts signal above the decoding threshold.\n"
            "More stations = band open. Diversity = system automatically picks the better antenna."
        ),

        # Erklärungs-Fußzeile Diversity-Diagramm (Platzhalter {band} und {protocol})
        "expl_diversity": (
            "Normal (grey): 1 antenna, like WSJT-X — baseline reference.\n"
            "Diversity Standard (blue): 2 antennas — automatically selects the antenna decoding more stations.\n"
            "Diversity DX (orange): 2 antennas — selects the antenna with more weak DX signals (SNR below −10 dB).\n"
            "Error bars (white marks): Day-to-day variation — the more days, the more stable the result.\n"
            "Green cap (+N): Stations ANT1 alone couldn't decode — ANT2 rescued them (signal below −24 dB).\n"
            "\n"
            "Raw data: statistics/{{mode}}/{band}/{protocol}/  ·  github.com/mikewanne/SimpleFT8"
        ),

        # Zeitbereich / Time range
        "no_data":  "no data",
        "date_to":  "to",

        # PDF Footer
        "footer_left": "SimpleFT8 Diversity Field Study — DA1MHH / Mike Hammerer  ·  {gen_date}",

        # Seitenzahl-Label / Page number label
        "page":     "Page {n}",

        # PDF Name
        "pdf_name": "SimpleFT8_Report.pdf",

        # ── Title page (p.1) ─────────────────────────────────────────────────
        "p1_title":    "SimpleFT8 — Two Antennas, One Comparison",
        "p1_subtitle": "What does Diversity actually deliver? — 40m FT8, first field results",
        "p1_period_label": "Period: {time_range}   ·   15s cycles evaluated: {total_cyc}",
        "p1_summary_title": "Summary:",
        "p1_summary_body": (
            "With Diversity Standard (blue) I decoded on average {s_gain} more stations than with a single antenna.\n"
            "Including 'rescued' stations, this rises to up to {s_gain_r}.\n"
            "Diversity DX (orange) delivers {d_gain} — less than Standard, but targeted at weak DX signals."
        ),
        "p1_caveat": (
            "Note: These are only 2 measurement days, morning hours only (05–12 UTC). "
            "The numbers may shift — but the trend is already clear."
        ),
        "p1_modes_title": "What do the three modes mean?",
        "p1_modes_body": (
            "Normal (grey): One antenna, no special logic — just like WSJT-X. This is the reference baseline.\n"
            "Diversity Standard (blue): Two antennas. The system automatically picks the antenna with more stations.\n"
            "Diversity DX (orange): Two antennas. Picks the antenna with the weakest DX signals (below −10 dB).\n"
            "Rescue (green caps): Stations ANT1 couldn't hear — ANT2 decoded them anyway."
        ),

        # ── Methodology page (p.2) ───────────────────────────────────────────
        "p2_header_title":    "How was it measured?",
        "p2_header_subtitle": "Setup, time period and a bit of background",
        "p2_setup_title": "The Setup",
        "p2_setup_body": (
            "Measured on 40m FT8 using a FlexRadio FLEX-8400M — two antenna ports, same frequency.\n"
            "Period: {time_range}, mornings between 05:00 and 12:00 UTC. Yes, nights are still missing — coming soon.\n"
            "Cycles: Normal {n_c} ({n_d} day/s) | Diversity Standard {s_c} ({s_d} day/s) | Diversity DX {d_c} ({d_d} day/s).\n"
            "Each FT8 cycle lasts 15 seconds — the app counts decoded stations per cycle."
        ),
        "p2_pooled_title": "Why not just use the daily average?",
        "p2_pooled_body": (
            "Good question — I did it that way at first too. But if one day had only 20 cycles and another had 500,\n"
            "the short day would carry the same weight. That's unfair. So all individual values are pooled and\n"
            "averaged directly — regardless of which day. This gives a picture much closer to reality."
        ),
        "p2_rescue_title": "What are 'rescued stations' (Rescue)?",
        "p2_rescue_body": (
            "Imagine a station transmitting so weakly that ANT1 receives it below −24 dB.\n"
            "That is the FT8 decoding threshold — below that, decoding is practically impossible.\n"
            "ANT2 receives the same station with slightly more signal and decodes it anyway.\n"
            "We call this 'Rescue'. The green caps in the charts show exactly these stations.\n"
            "Whether you count them or treat them separately — that's up to you. Both values are in this report."
        ),
        "p2_rawdata_title": "Where does the raw data come from?",
        "p2_rawdata_body": (
            "SimpleFT8 writes a small Markdown file per hour containing all cycle values.\n"
            "No pre-computed averages — raw data only. The analysis script calculates everything fresh.\n"
            "Want to check? statistics/ in the GitHub repo, all public."
        ),

        # ── Results page (p.3) ───────────────────────────────────────────────
        "p3_header_title":    "Main Results — Comparison Table",
        "p3_header_subtitle": "40m FT8 · Pooled Mean",
        "p3_col_labels": [
            "Mode", "Avg Sta.\n/Cycle", "vs Normal\nw/o Rescue",
            "vs Normal\n+ Rescue", "Rescue\nonly", "Days", "Cycles",
        ],
        "p3_note1": (
            "Avg Sta./Cycle = mean over all individual cycles directly (not first day averages).   "
            "Rescue = ANT1 below −24 dB, ANT2 decoded anyway."
        ),
        "p3_note2": (
            "Only 2 measurement days so far, mornings 05–12 UTC only — nights and evenings still missing. "
            "Numbers may shift as more data comes in."
        ),

        # ── Stations diagram page (p.4) ──────────────────────────────────────
        "p4_title":      "Stations per Hour — all three modes compared",
        "p4_subtitle":   "{band} {protocol} — line = mean, shaded band = day-to-day variation",
        "p4_annotation": (
            "You can clearly see how the grey line (Normal, one antenna) almost always falls below blue and orange. "
            "The shaded band shows day-to-day variation — as more days are added, the band will narrow."
        ),

        # ── Diversity diagram page (p.5) ─────────────────────────────────────
        "p5_title":      "Direct Comparison — bars per hour, three modes side by side",
        "p5_subtitle":   "{band} {protocol} — Normal (grey) | Diversity Standard (blue) | Diversity DX (orange) | Rescue caps (green)",
        "p5_annotation": (
            "Green caps (+N) on top of bars show stations that ANT1 couldn't decode — signal below −24 dB. "
            "ANT2 rescued them anyway. Whether to count them or not — your call. "
            "White error bars show day-to-day variation."
        ),

        # ── Rescue page (p.6) ────────────────────────────────────────────────
        "p6_header_title":    "The Green Caps — count them or not?",
        "p6_header_subtitle": "Rescue stations: What are they and what do they tell us?",
        "p6_about_title": "What's this about?",
        "p6_about_body": (
            "In the diversity chart you can see small green caps with a +N on top of some bars.\n"
            "These are stations ANT1 couldn't decode — their signal was below −24 dB, too weak.\n"
            "ANT2 still received and decoded them. Over the measurement period this averaged\n"
            "Ø {s_rsc:.1f} stations per hour for Diversity Standard, and Ø {d_rsc:.1f}/h for Diversity DX."
        ),
        "p6_pro_title": "Why should you count them in?",
        "p6_pro_body": (
            "Because the QSO is real for the operator — regardless of whether ANT1 or ANT2 made it possible.\n"
            "These stations would never have made it into the log with a single antenna.\n"
            "This is not a measurement artifact — it's exactly the point of running a second antenna.\n"
            "With Rescue: Standard {s_gain_r}, DX {d_gain_r} — that's the full picture."
        ),
        "p6_con_title": "Why might you leave them out?",
        "p6_con_body": (
            "SNR values fluctuate within the 15 seconds of a cycle — a station just\n"
            "below −24 dB might be above that threshold in the next cycle.\n"
            "The −24 dB threshold is an empirical value, not a law of nature.\n"
            "For a clean comparison with other systems, counting only what ANT1 directly decoded is more conservative."
        ),
        "p6_closing": (
            "That's why this report always shows both numbers: without Rescue (the conservative value) and "
            "with Rescue (what you get in real operation). Take whichever fits your perspective."
        ),

        # ── Conclusion page (p.7) ────────────────────────────────────────────
        "p7_header_title":    "What can you take away from this?",
        "p7_header_subtitle": "Conclusions and what gets measured next",
        "p7_visible_title": "What is clearly visible:",
        "p7_fazit_body": (
            "Diversity Standard consistently delivers between {gain_lo:.0f}% and {gain_hi:.0f}% more stations "
            "across both measurement days —\ndepending on whether you count rescued stations or not. "
            "This is not coincidence, it repeats.\n"
            "Diversity DX sits at {d_gain:.0f}% without Rescue — less than Standard, but DX deliberately "
            "optimises\nfor the weakest signals. If you do a lot of DX, that makes sense."
        ),
        "p7_fazit_best": (
            "\nThe strongest effect was at {hour:02d}:00 UTC with +{s_gain:.0f}% — "
            "typically the time when the band is just opening or closing."
        ),
        "p7_cannot_title": "What cannot be said yet:",
        "p7_cannot_body": (
            "Only 2 measurement days — enough to see a trend, but not enough for robust conclusions.\n"
            "Night and evening hours are completely missing — 40m is often significantly better in the evening.\n"
            "Contest operation, geomagnetic storms, poor conditions — not yet tested.\n"
            "Whether this works the same on other transceivers — unknown, tested only on the FLEX so far."
        ),
        "p7_next_title": "What comes next:",
        "p7_next_body": (
            "Night and evening measurements on 40m — that's the interesting part I don't have yet.\n"
            "More days so the bars in the chart stabilize and variation decreases.\n"
            "20m will come at some point — but only when there is enough data. Not before.\n"
            "This report updates automatically whenever new data comes in."
        ),
        "p7_raw_link": (
            "Raw data: statistics/  in the repo  ·  github.com/mikewanne/SimpleFT8  ·  DA1MHH"
        ),
    },
}

# Sanity check: both language dicts must have the same keys
assert TEXTS["de"].keys() == TEXTS["en"].keys(), (
    "Language key mismatch between 'de' and 'en' — fix TEXTS dict!"
)

# ── Markdown-Parser ───────────────────────────────────────────────────────────

def _normalize_col(raw: str) -> str:
    key = raw.strip().lower()
    return _COL_MAP.get(key, key.replace(" ", "_"))


def parse_md_table(filepath: Path) -> list[dict]:
    rows = []
    headers = None
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if not line.startswith("|"):
                if line.startswith("## "):
                    break
                continue
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p != ""]
            if not parts:
                continue
            if all(re.match(r"^[-:]+$", p) for p in parts):
                continue
            if headers is None:
                headers = [_normalize_col(p) for p in parts]
            else:
                row = {}
                for i, key in enumerate(headers):
                    row[key] = parts[i] if i < len(parts) else ""
                rows.append(row)
    return rows


def _to_float(val) -> float | None:
    try:
        return float(str(val).replace("+", ""))
    except (ValueError, AttributeError):
        return None


def _to_int(val) -> int | None:
    try:
        return int(val)
    except (ValueError, AttributeError):
        return None


def _file_hour(filepath: Path) -> int | None:
    try:
        return datetime.strptime(filepath.stem, "%Y-%m-%d_%H").hour
    except ValueError:
        return None


def _file_date(filepath: Path) -> str | None:
    try:
        return datetime.strptime(filepath.stem, "%Y-%m-%d_%H").strftime("%Y-%m-%d")
    except ValueError:
        return None


# ── Daten-Aggregation ─────────────────────────────────────────────────────────

def load_hourly_stats(stats_dir: Path, rx_mode: str, band: str,
                      protocol: str) -> dict[int, dict]:
    """Pro UTC-Stunde: alle Zyklen-Werte (pooled) + Tages-Granularität + Minuten-Abdeckung.

    Returns dict[hour → {"cycles": [int, ...], "daily": {date: [int, ...]}, "minutes": set}].
    Pooled Mean über alle Zyklen vermeidet den Bias, den mean-of-daily-means bei
    unterschiedlicher Zyklenanzahl pro Tag erzeugt.
    """
    mode_dir = stats_dir / rx_mode / band / protocol
    if not mode_dir.exists():
        return {}
    result: dict[int, dict] = {}
    for fp in sorted(mode_dir.glob("*.md")):
        h = _file_hour(fp)
        d = _file_date(fp)
        if h is None or d is None:
            continue
        rows = parse_md_table(fp)
        day_vals: list[int] = []
        minutes_set: set[int] = set()
        for r in rows:
            v = _to_int(r.get("stationen", ""))
            if v is not None:
                day_vals.append(v)
            t = r.get("zeit", "")
            m = re.match(r"\d{1,2}:(\d{2}):", t)
            if m:
                minutes_set.add(int(m.group(1)))
        if not day_vals:
            continue
        bucket = result.setdefault(h, {"cycles": [], "daily": {}, "minutes": set()})
        bucket["cycles"].extend(day_vals)
        bucket["daily"].setdefault(d, []).extend(day_vals)
        bucket["minutes"] |= minutes_set
    return result


def load_rescue_by_hour(stats_dir: Path, mode: str, band: str,
                        protocol: str) -> dict[int, float]:
    """Rescue-Events pro Stunde des Tages, gemittelt über Messtage."""
    stations_dir = stats_dir / mode / band / protocol / "stations"
    if not stations_dir.exists():
        return {}
    per_day_hour: dict[tuple, int] = defaultdict(int)
    for fp in sorted(stations_dir.glob("*.md")):
        h = _file_hour(fp)
        d = _file_date(fp)
        if h is None or d is None:
            continue
        for row in parse_md_table(fp):
            a1 = _to_float(row.get("ant1_db", ""))
            a2 = _to_float(row.get("ant2_db", ""))
            if a1 is not None and a2 is not None and a1 <= -24 and a2 > -24:
                per_day_hour[(d, h)] += 1
    hour_totals: dict[int, list[int]] = defaultdict(list)
    for (d, h), count in per_day_hour.items():
        hour_totals[h].append(count)
    return {h: sum(v) / len(v) for h, v in hour_totals.items()}


def _aggregate(hour_stats: dict[int, dict]) -> dict[int, dict]:
    """Pooled Mean (alle Zyklen) + Min/Max über Tages-Mittelwerte (für Error Bars)."""
    result = {}
    for hour, data in sorted(hour_stats.items()):
        cycles = data.get("cycles", [])
        if not cycles:
            continue
        pooled_mean = sum(cycles) / len(cycles)
        daily_means = [sum(v) / len(v) for v in data.get("daily", {}).values() if v]
        minutes = data.get("minutes", set())
        result[hour] = {
            "mean":       pooled_mean,
            "min":        min(daily_means) if len(daily_means) > 1 else pooled_mean,
            "max":        max(daily_means) if len(daily_means) > 1 else pooled_mean,
            "n_cycles":   len(cycles),
            "n_days":     len(daily_means),
            "coverage":   len(minutes),
        }
    return result


def _hours_x(agg: dict[int, dict]):
    if not agg:
        return [], [], [], []
    lo, hi = min(agg), max(agg)
    xs = list(range(lo, hi + 1))
    NaN = float("nan")
    means = [agg[h]["mean"] if h in agg else NaN for h in xs]
    mins  = [agg[h]["min"]  if h in agg else NaN for h in xs]
    maxs  = [agg[h]["max"]  if h in agg else NaN for h in xs]
    return xs, means, mins, maxs


def _n_days_label(agg: dict[int, dict], T: dict, label: str = "") -> str:
    """Returns a formatted basis entry using T['basis_entry'] template."""
    if not agg:
        return ""
    n_days = max(v["n_days"] for v in agg.values())
    n_cyc  = sum(v["n_cycles"] for v in agg.values())
    pl = T["day_plural_1"] if n_days == 1 else T["day_plural_n"]
    return T["basis_entry"].format(label=label, n_d=n_days, pl=pl, n_c=n_cyc)


# ── Gradient-Balken ───────────────────────────────────────────────────────────

def _gradient_bars(ax, x_positions, heights, width: float,
                   top_color: str, label: str | None = None,
                   alpha: float = 1.0, zorder: int = 2) -> mpatches.Patch | None:
    """Zeichnet Balken mit vertikalem Farbverlauf (BG → top_color)."""
    cmap = mc.LinearSegmentedColormap.from_list("g", [DARK_BG, top_color])
    gradient = np.linspace(0, 1, 256).reshape(256, 1)

    for x, h in zip(x_positions, heights):
        if h is None or h <= 0.001:
            continue
        ax.imshow(
            gradient, aspect="auto", origin="lower",
            extent=[x - width / 2, x + width / 2, 0, h],
            cmap=cmap, zorder=zorder, alpha=alpha,
        )

    if label:
        return mpatches.Patch(facecolor=top_color, alpha=0.85, label=label)
    return None


def _draw_rescue_caps(ax, x_positions, station_vals, rescue_vals,
                      bar_w: float, max_val: float) -> bool:
    """Grüne Rescue-Kappen oben auf Diversity-Balken + +N Labels."""
    drawn = False
    for xi, sv, rv in zip(x_positions, station_vals, rescue_vals):
        if rv < 0.5 or sv < 0.5:
            continue
        base = max(0.0, sv - rv)
        ax.bar(xi, rv, bottom=base, width=bar_w,
               color=COLORS["rescue"], alpha=0.92, zorder=3, linewidth=0)
        ax.text(xi, sv + max_val * 0.016, f"+{rv:.0f}",
                ha="center", va="bottom", fontsize=7,
                color=COLORS["rescue"], fontweight="bold", zorder=5)
        drawn = True
    return drawn


# ── Achsen-Setup ──────────────────────────────────────────────────────────────

def _setup_dark_ax(ax):
    ax.set_facecolor(DARK_BG)
    ax.tick_params(colors=DARK_FG, labelsize=8)
    ax.xaxis.label.set_color(DARK_FG)
    ax.yaxis.label.set_color(DARK_FG)
    ax.title.set_color(DARK_FG)
    for spine in ax.spines.values():
        spine.set_color(DARK_GRID)
    ax.grid(True, color=DARK_GRID, linewidth=0.5, alpha=0.6, zorder=0)


def _hour_ticks_line(ax, xs: list[int]):
    ax.set_xticks(list(range(0, 24)))
    ax.set_xticklabels(
        [f"{h:02d}:00" for h in range(24)],
        fontsize=7, color=DARK_FG, rotation=45, ha="right",
    )
    if xs:
        ax.set_xlim(max(0, min(xs) - 0.5), min(23, max(xs) + 0.5))


def _hour_ticks_bar(ax, x_pos: list[int], hours: list[int]):
    ax.set_xticks(x_pos)
    ax.set_xticklabels(
        [f"{h:02d}:00" for h in hours],
        fontsize=8, color=DARK_FG, rotation=45, ha="right",
    )


def _footer(fig, text: str):
    fig.text(
        0.01, 0.01, text,
        ha="left", va="bottom",
        fontsize=8, color="#aaaaaa",
        linespacing=1.6,
        transform=fig.transFigure,
    )


# ── Diagramm 1: Stationen über 24h ───────────────────────────────────────────

_MODE_ORDER   = ["Normal", "Diversity_Normal", "Diversity_Dx"]
_MODE_OFFSETS = {"Normal": -0.27, "Diversity_Normal": 0.0, "Diversity_Dx": +0.27}


def create_stations_diagram(band: str, protocol: str, output_dir: Path,
                             lang: str = "de"):
    T = TEXTS[lang]
    mode_labels = T["mode_labels"]

    fig, ax = plt.subplots(figsize=(14, 6.5), facecolor=DARK_BG)
    _setup_dark_ax(ax)

    has_data = False
    all_xs: list[int] = []

    for rx_mode in RX_MODES:
        hour_vals = load_hourly_stats(STATS_DIR, rx_mode, band, protocol)
        if not hour_vals:
            continue
        agg = _aggregate(hour_vals)
        xs, means, mins, maxs = _hours_x(agg)
        if not xs:
            continue
        all_xs.extend(xs)
        n_d = max(v["n_days"] for v in agg.values())
        n_c = sum(v["n_cycles"] for v in agg.values())
        pl = T["day_plural_1"] if n_d == 1 else T["day_plural_n"]
        sep = T["thousands_sep"]
        n_c_fmt = f"{n_c:,}".replace(",", sep)
        base_label = mode_labels.get(rx_mode, rx_mode.replace("_", " "))
        label = T["basis_entry"].format(label=base_label, n_d=n_d, pl=pl, n_c_fmt=n_c_fmt)

        color = COLORS[rx_mode]
        ax.plot(xs, means, color=color, label=label, linewidth=2.5, zorder=3)
        ax.fill_between(xs, mins, maxs, color=color, alpha=0.15, zorder=2)
        has_data = True

        # Gestrichelte Rescue-Linie (mean + Rescue) für Diversity-Modi
        if rx_mode in COLORS_RESCUE:
            rescue = load_rescue_by_hour(STATS_DIR, rx_mode, band, protocol)
            if rescue:
                xs_r = [h for h in xs if h in agg]
                ys_r = [agg[h]["mean"] + rescue.get(h, 0.0) for h in xs_r]
                dark = COLORS_RESCUE[rx_mode]
                ax.plot(xs_r, ys_r, color=dark, linewidth=1.2, linestyle="--",
                        alpha=0.80, zorder=3,
                        label=f"{base_label}\n{T['rescue_line']}")

    if not has_data:
        plt.close(fig)
        return

    _hour_ticks_line(ax, all_xs)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.set_xlabel(T["x_label"], color=DARK_FG, labelpad=6)
    ax.set_ylabel(T["y_label_line"], color=DARK_FG)
    ax.set_title(
        T["title_stations"].format(band=band, protocol=protocol),
        color=DARK_FG, fontsize=13, pad=10,
    )
    leg = ax.legend(
        ncol=5,
        loc="upper left",
        bbox_to_anchor=(0, -0.22, 1, 0),
        mode="expand",
        facecolor="#2a2a2a",
        edgecolor=DARK_GRID,
        framealpha=0.9,
    )
    for t in leg.get_texts():
        t.set_color(DARK_FG)

    _footer(fig, T["expl_stations"])
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.48, right=0.98)

    out = output_dir / f"stationen_{band}_{protocol}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    print(f"  ✓ {out.relative_to(BASE_DIR)}")


# ── Diagramm 2: 3-Modus Vergleich (Normal | Diversity Standard | Diversity DX) ─

def create_diversity_diagram(band: str, protocol: str, output_dir: Path,
                              lang: str = "de"):
    T = TEXTS[lang]
    mode_labels = T["mode_labels"]
    bar_w = 0.22

    agg_all: dict[str, dict] = {}
    rescue_all: dict[str, dict] = {}
    for mode in _MODE_ORDER:
        hv = load_hourly_stats(STATS_DIR, mode, band, protocol)
        if hv:
            agg_all[mode] = _aggregate(hv)
        if mode != "Normal":
            r = load_rescue_by_hour(STATS_DIR, mode, band, protocol)
            if r:
                rescue_all[mode] = r

    if not agg_all:
        return

    all_hours = sorted(set().union(*[set(a.keys()) for a in agg_all.values()]))
    n = len(all_hours)
    if n == 0:
        return

    x_base = np.arange(n, dtype=float)

    fig, ax = plt.subplots(figsize=(16, 6.5), facecolor=DARK_BG)
    _setup_dark_ax(ax)

    # max_val inkl. Rescue-Kappen und Min/Max-Error-Bars, damit +N Labels + Whisker
    # nicht über den ylim hinausragen
    max_candidates = [1.0]
    for mode in _MODE_ORDER:
        if mode not in agg_all:
            continue
        rescue = rescue_all.get(mode, {})
        for h in all_hours:
            if h not in agg_all[mode]:
                continue
            a = agg_all[mode][h]
            cap = a["mean"] + rescue.get(h, 0.0)
            whisker_top = a["max"]
            max_candidates.append(max(cap, whisker_top))
    max_val = max(max_candidates)
    ax.set_ylim(0, max_val * 1.30)
    ax.set_xlim(-0.6, n - 0.4)

    handles = []
    for mode in _MODE_ORDER:
        if mode not in agg_all:
            continue
        agg = agg_all[mode]
        x_pos = x_base + _MODE_OFFSETS[mode]
        heights = [agg[h]["mean"] if h in agg else 0.0 for h in all_hours]
        n_d = max(v["n_days"] for v in agg.values())
        n_c = sum(v["n_cycles"] for v in agg.values())
        pl = T["day_plural_1"] if n_d == 1 else T["day_plural_n"]
        sep = T["thousands_sep"]
        n_c_fmt = f"{n_c:,}".replace(",", sep)
        base_label = mode_labels.get(mode, mode.replace("_", " "))
        label = T["basis_entry"].format(label=base_label, n_d=n_d, pl=pl, n_c_fmt=n_c_fmt)
        patch = _gradient_bars(ax, x_pos, heights, bar_w,
                               COLORS[mode], label=label, zorder=2)
        if patch:
            handles.append(patch)

        # Error-Bars (Tag-zu-Tag-Variabilität) nur wenn mehrere Messtage vorhanden
        err_x, err_mean, err_lo, err_hi = [], [], [], []
        for idx, h in enumerate(all_hours):
            if h not in agg or agg[h]["n_days"] < 2:
                continue
            a = agg[h]
            err_x.append(x_pos[idx])
            err_mean.append(a["mean"])
            err_lo.append(max(0.0, a["mean"] - a["min"]))
            err_hi.append(max(0.0, a["max"] - a["mean"]))
        if err_x:
            ax.errorbar(err_x, err_mean, yerr=[err_lo, err_hi], fmt="none",
                        ecolor=DARK_FG, alpha=0.55, capsize=2.5,
                        elinewidth=0.9, zorder=4)

    any_rescue = False
    for mode in ["Diversity_Normal", "Diversity_Dx"]:
        if mode not in agg_all:
            continue
        agg = agg_all[mode]
        rescue = rescue_all.get(mode, {})
        x_pos = x_base + _MODE_OFFSETS[mode]
        sv_list = [agg[h]["mean"] if h in agg else 0.0 for h in all_hours]
        rv_list  = [rescue.get(h, 0.0) for h in all_hours]
        if _draw_rescue_caps(ax, x_pos, sv_list, rv_list, bar_w, max_val):
            any_rescue = True

    if any_rescue:
        handles.append(mpatches.Patch(facecolor=COLORS["rescue"], alpha=0.92,
                                      label=T["rescue_legend"]))

    _hour_ticks_bar(ax, list(x_base), all_hours)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.set_xlabel(T["x_label"], color=DARK_FG, labelpad=6)
    ax.set_ylabel(T["y_label_bar"], color=DARK_FG)

    ax.set_title(
        T["title_diversity"].format(band=band, protocol=protocol),
        color=DARK_FG, fontsize=13, pad=10,
    )

    leg = ax.legend(handles=handles, facecolor="#2a2a2a",
                    edgecolor=DARK_GRID, framealpha=0.9, loc="upper left")
    for t in leg.get_texts():
        t.set_color(DARK_FG)

    expl = T["expl_diversity"].format(band=band, protocol=protocol)
    _footer(fig, expl)
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.36, right=0.98)

    out = output_dir / f"diversity_{band}_{protocol}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    print(f"  ✓ {out.relative_to(BASE_DIR)}")


# ── PDF-Bericht ───────────────────────────────────────────────────────────────

def _extract_time_range(stats_dir: Path, T: dict) -> str:
    dates = []
    for md_file in stats_dir.rglob("*.md"):
        d = _file_date(md_file)
        if d:
            dates.append(d)
    if not dates:
        return T["no_data"]
    ds = sorted(set(dates))
    return ds[0] if len(ds) == 1 else f"{ds[0]} {T['date_to']} {ds[-1]}"


def _combo_summary(stats_dir: Path, band: str, protocol: str) -> dict:
    """Pooled Mean + gewichteter Rescue-Schnitt pro Modus."""
    result: dict[str, dict] = {}
    for mode in RX_MODES:
        hv = load_hourly_stats(stats_dir, mode, band, protocol)
        if not hv:
            continue
        agg = _aggregate(hv)
        if not agg:
            continue
        total_w = sum(v["mean"] * v["n_cycles"] for v in agg.values())
        total_c = sum(v["n_cycles"] for v in agg.values())
        n_days  = max(v["n_days"] for v in agg.values())
        result[mode] = {
            "avg":      total_w / total_c if total_c else 0.0,
            "n_days":   n_days,
            "n_cycles": total_c,
        }
        if mode != "Normal":
            rescue = load_rescue_by_hour(stats_dir, mode, band, protocol)
            if rescue:
                r_w = sum(rescue[h] * agg[h]["n_cycles"] for h in rescue if h in agg)
                r_c = sum(agg[h]["n_cycles"] for h in rescue if h in agg)
                result[mode]["avg_rescue"] = r_w / r_c if r_c else 0.0
            else:
                result[mode]["avg_rescue"] = 0.0
    return result


# ── PDF Bericht — Cursor-Layout (inch-basiert, kein hardcoded y) ──────────────

_R_BG     = "#ffffff"
_R_FG     = "#1a1a1a"
_R_ACCENT = "#1a3a5c"
_R_SUB    = "#666666"
_R_GRID   = "#cccccc"
_R_GREEN  = "#1a5c2a"
_R_ORANGE = "#994400"

_PH   = 8.27    # Seitenhöhe Zoll (A4 landscape)
_PW   = 11.69   # Seitenbreite Zoll
_ML   = 0.55    # linker Rand Zoll
_HBAR = 0.78    # Header-Balkenhöhe Zoll
_FBAR = 0.46    # Footer-Balkenhöhe Zoll
_CTOP = _HBAR + 0.22    # Inhalt beginnt hier (Zoll von oben)
_CBOT = _PH - _FBAR - 0.10  # Inhalt endet hier (Zoll von oben)


def _yf(y_in: float) -> float:
    """Zoll von oben → figure-Koordinate (0=unten, 1=oben)."""
    return 1.0 - y_in / _PH


def _rfig() -> plt.Figure:
    fig = plt.figure(figsize=(_PW, _PH))
    fig.patch.set_facecolor(_R_BG)
    return fig


def _r_header(fig: plt.Figure, title: str, subtitle: str = "") -> None:
    from matplotlib.patches import Rectangle
    fig.add_artist(Rectangle((0, _yf(_HBAR)), 1, _HBAR / _PH,
                              transform=fig.transFigure,
                              facecolor=_R_ACCENT, edgecolor="none", zorder=5))
    fig.text(0.04, _yf(_HBAR * 0.52), title, fontsize=15, color="white",
             fontweight="bold", va="center", transform=fig.transFigure, zorder=6)
    if subtitle:
        fig.text(0.04, _yf(_HBAR * 0.85), subtitle, fontsize=10, color="#aaccee",
                 va="center", transform=fig.transFigure, zorder=6)


def _r_footer(fig: plt.Figure, gen_date: str, T: dict, page: str = "") -> None:
    from matplotlib.patches import Rectangle
    fig.add_artist(Rectangle((0, 0), 1, _FBAR / _PH,
                              transform=fig.transFigure,
                              facecolor="#eeeeee", edgecolor="none", zorder=5))
    fig.text(0.04, _FBAR / _PH / 2,
             T["footer_left"].format(gen_date=gen_date),
             fontsize=8.5, color=_R_SUB, va="center",
             transform=fig.transFigure, zorder=6)
    if page:
        fig.text(0.97, _FBAR / _PH / 2, f"github.com/mikewanne/SimpleFT8  ·  {page}",
                 fontsize=8.5, color=_R_SUB, va="center", ha="right",
                 transform=fig.transFigure, zorder=6)


def _ctext(fig: plt.Figure, y_in: float, text: str, fs: float,
           color: str = _R_FG, bold: bool = False,
           italic: bool = False, ls: float = 1.5) -> float:
    """Text bei y_in Zoll von oben platzieren. Gibt y_in nach dem Text zurück."""
    n = max(1, text.count('\n') + 1)
    fig.text(_ML / _PW, _yf(y_in), text,
             fontsize=fs, color=color,
             fontweight="bold" if bold else "normal",
             style="italic" if italic else "normal",
             va="top", linespacing=ls,
             transform=fig.transFigure)
    return y_in + n * fs / 72 * ls


def _chline(fig: plt.Figure, y_in: float, gap: float = 0.06) -> float:
    """Horizontale Trennlinie. Gibt y_in nach der Linie zurück."""
    from matplotlib.lines import Line2D
    yf = _yf(y_in + gap / 2)
    fig.add_artist(Line2D([_ML / _PW, 1 - _ML / _PW], [yf, yf],
                          transform=fig.transFigure,
                          color=_R_GRID, linewidth=0.8, zorder=4))
    return y_in + gap


def _csection(fig: plt.Figure, y_in: float, title: str, body: str,
              t_fs: float = 13, b_fs: float = 11,
              t_color: str = _R_ACCENT, gap: float = 0.30) -> float:
    """Vollständiger Abschnitt: Titel + Linie + Text. Cursor-Rückgabe."""
    y_in = _ctext(fig, y_in, title, t_fs, color=t_color, bold=True)
    y_in = _chline(fig, y_in, gap=0.07)
    y_in = _ctext(fig, y_in, body, b_fs)
    return y_in + gap


def _hourly_analysis(stats_dir: Path, band: str, protocol: str) -> list[dict]:
    agg_n  = _aggregate(load_hourly_stats(stats_dir, "Normal",           band, protocol))
    agg_s  = _aggregate(load_hourly_stats(stats_dir, "Diversity_Normal", band, protocol))
    agg_d  = _aggregate(load_hourly_stats(stats_dir, "Diversity_Dx",     band, protocol))
    resc_s = load_rescue_by_hour(stats_dir, "Diversity_Normal", band, protocol)
    resc_d = load_rescue_by_hour(stats_dir, "Diversity_Dx",     band, protocol)
    hours  = sorted(set(agg_n) & (set(agg_s) | set(agg_d)))
    result = []
    for h in hours:
        nm = agg_n[h]["mean"] if h in agg_n else None
        sm = agg_s[h]["mean"] if h in agg_s else None
        dm = agg_d[h]["mean"] if h in agg_d else None
        sg = (sm / nm - 1) * 100 if (nm and sm and nm > 0) else None
        dg = (dm / nm - 1) * 100 if (nm and dm and nm > 0) else None
        result.append({"hour": h, "n_mean": nm, "s_mean": sm, "d_mean": dm,
                        "s_gain": sg, "d_gain": dg,
                        "rs": resc_s.get(h, 0.0), "rd": resc_d.get(h, 0.0)})
    return result


def _r_title_page(pdf: PdfPages, summary: dict, time_range: str,
                  gen_date: str, T: dict) -> None:
    from matplotlib.patches import Rectangle
    fig = _rfig()
    TH = 1.50
    fig.add_artist(Rectangle((0, _yf(TH)), 1, TH / _PH,
                              transform=fig.transFigure,
                              facecolor=_R_ACCENT, edgecolor="none", zorder=5))
    fig.text(0.50, _yf(TH * 0.40), T["p1_title"],
             fontsize=22, color="white", fontweight="bold",
             ha="center", va="center", transform=fig.transFigure, zorder=6)
    fig.text(0.50, _yf(TH * 0.76), T["p1_subtitle"],
             fontsize=13, color="#aaccee", ha="center", va="center",
             transform=fig.transFigure, zorder=6)

    total_cyc = sum(s.get("n_cycles", 0) for s in summary.values())
    n_avg = summary.get("Normal",           {}).get("avg", 0.0)
    s_avg = summary.get("Diversity_Normal", {}).get("avg", 0.0)
    d_avg = summary.get("Diversity_Dx",     {}).get("avg", 0.0)
    s_rsc = summary.get("Diversity_Normal", {}).get("avg_rescue", 0.0)
    d_rsc = summary.get("Diversity_Dx",     {}).get("avg_rescue", 0.0)
    def pct(a, b): return f"{(a / b - 1) * 100:+.0f}%" if b > 0 else "n/a"

    y = TH + 0.22
    y = _ctext(fig, y,
               T["p1_period_label"].format(time_range=time_range, total_cyc=total_cyc),
               10, color=_R_SUB)
    y += 0.18

    y = _csection(fig, y, T["p1_summary_title"],
                  T["p1_summary_body"].format(
                      s_gain=pct(s_avg, n_avg),
                      s_gain_r=pct(s_avg + s_rsc, n_avg),
                      d_gain=pct(d_avg, n_avg),
                  ),
                  t_fs=13, b_fs=11, gap=0.20)

    y = _ctext(fig, y, T["p1_caveat"], 10.5, color=_R_ORANGE, italic=True)
    y += 0.28

    _csection(fig, y, T["p1_modes_title"], T["p1_modes_body"],
              t_fs=13, b_fs=11, gap=0.15)

    _r_footer(fig, gen_date, T, T["page"].format(n=1))
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def _r_methodik_page(pdf: PdfPages, summary: dict, time_range: str,
                     gen_date: str, T: dict) -> None:
    fig = _rfig()
    _r_header(fig, T["p2_header_title"], T["p2_header_subtitle"])

    n_d = summary.get('Normal',           {}).get('n_days',   '–')
    n_c = summary.get('Normal',           {}).get('n_cycles', '–')
    s_d = summary.get('Diversity_Normal', {}).get('n_days',   '–')
    s_c = summary.get('Diversity_Normal', {}).get('n_cycles', '–')
    d_d = summary.get('Diversity_Dx',     {}).get('n_days',   '–')
    d_c = summary.get('Diversity_Dx',     {}).get('n_cycles', '–')

    y = _CTOP
    y = _csection(fig, y, T["p2_setup_title"],
                  T["p2_setup_body"].format(
                      time_range=time_range,
                      n_c=n_c, n_d=n_d, s_c=s_c, s_d=s_d, d_c=d_c, d_d=d_d,
                  ),
                  t_fs=13, b_fs=11, gap=0.25)

    y = _csection(fig, y, T["p2_pooled_title"], T["p2_pooled_body"],
                  t_fs=13, b_fs=11, gap=0.25)

    y = _csection(fig, y, T["p2_rescue_title"], T["p2_rescue_body"],
                  t_fs=13, b_fs=11, gap=0.25)

    _csection(fig, y, T["p2_rawdata_title"], T["p2_rawdata_body"],
              t_fs=13, b_fs=11, gap=0.15)

    _r_footer(fig, gen_date, T, T["page"].format(n=2))
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def _r_ergebnisse_page(pdf: PdfPages, summary: dict, gen_date: str, T: dict) -> None:
    n_avg = summary.get("Normal", {}).get("avg", 0.0)
    mode_labels = T["mode_labels"]
    col_labels = T["p3_col_labels"]
    mode_meta = {
        "Normal":           (mode_labels["Normal"],           "#e8eef5", _R_ACCENT),
        "Diversity_Normal": (mode_labels["Diversity_Normal"], "#e8f5eb", _R_GREEN),
        "Diversity_Dx":     (mode_labels["Diversity_Dx"],    "#fff3e0", _R_ORANGE),
    }
    rows, row_face, row_text = [], [], []
    for mode in RX_MODES:
        if mode not in summary:
            continue
        s = summary[mode]
        avg = s["avg"]
        lbl, face, tcol = mode_meta[mode]
        if mode == "Normal" or n_avg <= 0:
            vs, vsr, r = "—", "—", "—"
        else:
            rsc = s.get("avg_rescue", 0.0)
            vs  = f"+{(avg / n_avg - 1) * 100:.0f}%"
            vsr = f"+{((avg + rsc) / n_avg - 1) * 100:.0f}%"
            r   = f"+{(rsc / n_avg) * 100:.0f}%"
        rows.append([lbl, f"{avg:.1f}", vs, vsr, r, str(s["n_days"]), str(s["n_cycles"])])
        row_face.append(face)
        row_text.append(tcol)

    if not rows:
        return

    fig = _rfig()
    _r_header(fig, T["p3_header_title"], T["p3_header_subtitle"])

    table_top    = _yf(_CTOP + 0.10)
    table_bottom = _yf(6.50)
    table_h      = table_top - table_bottom

    ax = fig.add_axes([0.04, table_bottom, 0.92, table_h])
    ax.axis("off")
    tbl = ax.table(cellText=rows, colLabels=col_labels, cellLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(12)
    tbl.scale(1, 3.2)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor(_R_GRID)
        if r == 0:
            cell.set_facecolor(_R_ACCENT)
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor(row_face[r - 1])
            cell.set_text_props(color=row_text[r - 1],
                                fontweight="bold" if c in (2, 3, 4) else "normal")

    y = 6.55
    y = _ctext(fig, y, T["p3_note1"], 9, color=_R_SUB)
    y += 0.06
    _ctext(fig, y, T["p3_note2"], 9, color=_R_ORANGE, italic=True)

    _r_footer(fig, gen_date, T, T["page"].format(n=3))
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def _r_diagramm_page(pdf: PdfPages, png_path: Path, title: str,
                     subtitle: str, annotation: str, gen_date: str, T: dict,
                     page: str = "") -> None:
    if not png_path.exists():
        return
    img = plt.imread(str(png_path))
    h_px, w_px = img.shape[:2]
    aspect = h_px / w_px
    fig = _rfig()
    _r_header(fig, title, subtitle)
    img_h = 0.62
    img_w = min(0.92, img_h / aspect * (8.27 / 11.69))
    ax_img = fig.add_axes([(1.0 - img_w) / 2, 0.20, img_w, img_h])
    ax_img.imshow(img)
    ax_img.axis("off")
    if annotation:
        fig.text(0.05, 0.155, annotation, fontsize=8.5, color=_R_SUB,
                 style="italic", transform=fig.transFigure, wrap=True)
    _r_footer(fig, gen_date, T, page)
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def _r_rescue_page(pdf: PdfPages, summary: dict, gen_date: str, T: dict) -> None:
    fig = _rfig()
    _r_header(fig, T["p6_header_title"], T["p6_header_subtitle"])

    n_avg = summary.get("Normal",           {}).get("avg", 0.0)
    s_avg = summary.get("Diversity_Normal", {}).get("avg", 0.0)
    d_avg = summary.get("Diversity_Dx",     {}).get("avg", 0.0)
    s_rsc = summary.get("Diversity_Normal", {}).get("avg_rescue", 0.0)
    d_rsc = summary.get("Diversity_Dx",     {}).get("avg_rescue", 0.0)
    def pct(a, b): return f"{(a / b - 1) * 100:+.0f}%" if b > 0 else "n/a"

    y = _CTOP
    y = _csection(fig, y, T["p6_about_title"],
                  T["p6_about_body"].format(s_rsc=s_rsc, d_rsc=d_rsc),
                  t_fs=13, b_fs=11, gap=0.25)

    y = _csection(fig, y, T["p6_pro_title"],
                  T["p6_pro_body"].format(
                      s_gain_r=pct(s_avg + s_rsc, n_avg),
                      d_gain_r=pct(d_avg + d_rsc, n_avg),
                  ),
                  t_fs=13, b_fs=11, t_color=_R_GREEN, gap=0.25)

    y = _csection(fig, y, T["p6_con_title"], T["p6_con_body"],
                  t_fs=13, b_fs=11, t_color=_R_ORANGE, gap=0.25)

    y = _chline(fig, y, gap=0.12)
    _ctext(fig, y, T["p6_closing"], 11, color=_R_ACCENT, italic=True)

    _r_footer(fig, gen_date, T, T["page"].format(n=6))
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def _r_fazit_page(pdf: PdfPages, summary: dict, hourly: list[dict],
                  gen_date: str, T: dict) -> None:
    fig = _rfig()
    _r_header(fig, T["p7_header_title"], T["p7_header_subtitle"])

    n_avg = summary.get("Normal",           {}).get("avg", 0.0)
    s_avg = summary.get("Diversity_Normal", {}).get("avg", 0.0)
    d_avg = summary.get("Diversity_Dx",     {}).get("avg", 0.0)
    s_rsc = summary.get("Diversity_Normal", {}).get("avg_rescue", 0.0)
    d_rsc = summary.get("Diversity_Dx",     {}).get("avg_rescue", 0.0)
    best_s = max((r for r in hourly if r["s_gain"] is not None),
                 key=lambda r: r["s_gain"], default=None)

    gain_lo = (s_avg / n_avg - 1) * 100 if n_avg > 0 else 0.0
    gain_hi = ((s_avg + s_rsc) / n_avg - 1) * 100 if n_avg > 0 else 0.0
    d_gain  = (d_avg / n_avg - 1) * 100 if n_avg > 0 else 0.0

    fazit = T["p7_fazit_body"].format(gain_lo=gain_lo, gain_hi=gain_hi, d_gain=d_gain)
    if best_s:
        fazit += T["p7_fazit_best"].format(hour=best_s["hour"], s_gain=best_s["s_gain"])

    y = _CTOP
    y = _csection(fig, y, T["p7_visible_title"], fazit, t_fs=13, b_fs=11, gap=0.25)

    y = _csection(fig, y, T["p7_cannot_title"], T["p7_cannot_body"],
                  t_fs=13, b_fs=11, t_color=_R_ORANGE, gap=0.25)

    y = _csection(fig, y, T["p7_next_title"], T["p7_next_body"],
                  t_fs=13, b_fs=11, gap=0.20)

    y = _chline(fig, y, gap=0.12)
    _ctext(fig, y, T["p7_raw_link"], 9, color=_R_SUB, italic=True)

    _r_footer(fig, gen_date, T, T["page"].format(n=7))
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def create_pdf_report(combos: set[tuple[str, str]], output_dir: Path,
                      lang: str = "de") -> None:
    T = TEXTS[lang]
    target = [c for c in sorted(combos) if c == ("40m", "FT8")]
    if not target:
        for band, protocol in sorted(combos):
            s = _combo_summary(STATS_DIR, band, protocol)
            if s.get("Normal", {}).get("n_days", 0) >= 1:
                target = [(band, protocol)]
                break
    if not target:
        print(f"  [!] No sufficient data for PDF report ({lang}).")
        return

    band, protocol = target[0]
    summary    = _combo_summary(STATS_DIR, band, protocol)
    hourly     = _hourly_analysis(STATS_DIR, band, protocol)
    normal_dir = STATS_DIR / "Normal" / band / protocol
    time_range = _extract_time_range(
        normal_dir if normal_dir.exists() else STATS_DIR, T
    )
    gen_date   = datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf_path   = output_dir / T["pdf_name"]

    with PdfPages(str(pdf_path)) as pdf:
        _r_title_page(pdf, summary, time_range, gen_date, T)           # p.1
        _r_methodik_page(pdf, summary, time_range, gen_date, T)        # p.2
        _r_ergebnisse_page(pdf, summary, gen_date, T)                  # p.3
        _r_diagramm_page(                                               # p.4
            pdf, output_dir / f"stationen_{band}_{protocol}.png",
            T["p4_title"],
            T["p4_subtitle"].format(band=band, protocol=protocol),
            T["p4_annotation"],
            gen_date, T, T["page"].format(n=4),
        )
        _r_diagramm_page(                                               # p.5
            pdf, output_dir / f"diversity_{band}_{protocol}.png",
            T["p5_title"],
            T["p5_subtitle"].format(band=band, protocol=protocol),
            T["p5_annotation"],
            gen_date, T, T["page"].format(n=5),
        )
        _r_rescue_page(pdf, summary, gen_date, T)                      # p.6
        _r_fazit_page(pdf, summary, hourly, gen_date, T)               # p.7

        d = pdf.infodict()
        d["Title"]   = f"SimpleFT8 Diversity — {band} {protocol}"
        d["Author"]  = "DA1MHH / Mike Hammerer"
        d["Subject"] = "Dual-Antenna Diversity Field Study"

    print(f"  ✓ PDF ({lang.upper()}): {pdf_path.relative_to(BASE_DIR)} (7 pages, {band} {protocol})")


# ── Haupt ─────────────────────────────────────────────────────────────────────

def discover_bands_protocols() -> set[tuple[str, str]]:
    combos: set[tuple[str, str]] = set()
    if not STATS_DIR.exists():
        return combos
    for mode_dir in STATS_DIR.iterdir():
        if not mode_dir.is_dir() or mode_dir.name not in RX_MODES:
            continue
        for band_dir in mode_dir.iterdir():
            if not band_dir.is_dir():
                continue
            for proto_dir in band_dir.iterdir():
                if proto_dir.is_dir() and proto_dir.name != "stations":
                    combos.add((band_dir.name, proto_dir.name))
    return combos


def main():
    combos = discover_bands_protocols()
    if not combos:
        print(f"Keine Daten in {STATS_DIR}.")
        sys.exit(0)

    for lang, out_dir in LANG_DIR.items():
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n{'='*50}")
        print(f"  Generating {lang.upper()} output → {out_dir.relative_to(BASE_DIR)}/")
        print(f"{'='*50}")
        for band, protocol in sorted(combos):
            print(f"\n  --- {band} / {protocol} ---")
            create_stations_diagram(band, protocol, out_dir, lang=lang)
            create_diversity_diagram(band, protocol, out_dir, lang=lang)
        print(f"\n  --- PDF ({lang.upper()}) ---")
        create_pdf_report(combos, out_dir, lang=lang)

    print(f"\nDone. Output in: {OUTPUT_DIR}  and  {OUTPUT_DIR_EN}")


if __name__ == "__main__":
    main()
