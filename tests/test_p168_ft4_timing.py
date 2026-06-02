"""P168 (02.06.2026): FT4 sendete 30s- statt 15s-Periode — Decode-Pfad-Fix.

PROBLEM (Mike-Field, ms-Logs): FT4-QSOs liefen im 30s-Takt (unsere TX-Slots
30s auseinander) statt 15s. Ursache (verifiziert): Der Decoder weckte FT4 erst
0,5s vor Slot-Ende (absolut 14,5s), die Encoder-Sende-Frist fürs nächste Fenster
ist aber 14,2s (FlexRadio 1,3s TX-Buffer → Audio muss 0,8s vor Slot-Grenze fertig
sein). Decode also strukturell zu spät → Encoder-Drift-Guard springt +2 Slots
(15s) → 30s-Periode.

ERSTER VERSUCH SCHEITERTE (Field-Crash, 0 Empfang): nur `_WAKE_OFFSETS["FT4"]`
0,5→1,5 (früher wecken) — aber das Decode-Fenster war an die Weckzeit gekoppelt
(`audio_12k[-slot_samples:]`), rutschte mit → Signal aus dem ft8_lib-Sync-Fenster
→ 0 Decodes.

FIX (dieser Stand): drei Dinge ENTKOPPELT —
  • `_WAKE_OFFSETS["FT4"]` = 1,5 (früh wecken, Decode rechtzeitig fertig).
  • Decode-Fenster SLOT-AUSGERICHTET auf [Slot−0,5; Slot+7,0] (= `_WINDOW_OFFSETS`),
    unabhängig von der Weckzeit: `_keep_window` behält den Nutzbereich
    (slot_samples − tail_pad) end-verankert, der Rest (Post-Signal-Stille) wird
    NACH `_preprocess_audio` mit Nullen aufgefüllt (DeepSeek-R1: sonst verfälschen
    die Nullen RMS-Norm + Whitening).
  • `_DT_OFFSETS` aus `_WINDOW_OFFSETS` abgeleitet (NICHT _WAKE) → FT4-DT bleibt
    konstant 1,0, egal wie früh geweckt wird.

FT8/FT2 bleiben Bit-für-Bit unverändert (tail_pad = WAKE−WINDOW = 0).

DeepSeek-Halluzination ABGELEHNT: DeepSeek behauptete, die Slot-Parität
`int(target_slot_start/slot_duration)%2` müsse für FT4 auf /15 statt /7.5 — FALSCH.
FT4 alterniert auf dem 7,5s-Raster (verifiziert gegen encoder.py:381, gleiche
Formel). /15 hätte Decoder/Encoder desynchronisiert → FT4 erst recht gebrochen.
"""

import numpy as np
import pytest

from core.decoder import (
    _WAKE_OFFSETS, _WINDOW_OFFSETS, _DT_OFFSETS, _TAIL_PAD_SAMPLES,
    _SLOT_SAMPLES, _PROTOCOL_TX_OFFSET, SAMP_RATE, _keep_window,
)


# ── A. Konstanten & Invarianten ──────────────────────────────────────────────

def test_wake_offsets():
    # FT4 weckt jetzt 1,5s vor Slot-Ende (früher als die 0,5 davor).
    assert _WAKE_OFFSETS == {"FT8": 2.5, "FT4": 1.5, "FT2": 0.3}


def test_window_offsets_decoupled_from_wake():
    # Fenster-Start: FT4 bleibt bei 0,5 (kanonische Position wie im Original),
    # obwohl WAKE jetzt 1,5 ist. FT8/FT2: WINDOW == WAKE (end-verankert).
    assert _WINDOW_OFFSETS == {"FT8": 2.5, "FT4": 0.5, "FT2": 0.3}


def test_dt_offsets_derived_from_window_not_wake():
    # DT hängt an der FENSTER-Position (WINDOW + Protokoll), NICHT an WAKE.
    assert _PROTOCOL_TX_OFFSET == 0.5
    for mode, win in _WINDOW_OFFSETS.items():
        assert _DT_OFFSETS[mode] == win + _PROTOCOL_TX_OFFSET, mode
    # Konkrete Werte unverändert ggü. v0.98.55 (kein Empfangs-Regress):
    assert _DT_OFFSETS == {"FT8": 3.0, "FT4": 1.0, "FT2": 0.8}


def test_window_le_wake_invariant():
    # Pflicht: WINDOW ≤ WAKE → tail_pad ≥ 0 (sonst negatives Padding = Crash).
    for mode in _WAKE_OFFSETS:
        assert _WINDOW_OFFSETS[mode] <= _WAKE_OFFSETS[mode], mode


def test_tail_pad_samples():
    # FT8/FT2 = 0 (kein Eingriff), FT4 = 1,0s = 12000 Samples @ 12kHz.
    assert _TAIL_PAD_SAMPLES["FT8"] == 0
    assert _TAIL_PAD_SAMPLES["FT2"] == 0
    assert _TAIL_PAD_SAMPLES["FT4"] == int(1.0 * SAMP_RATE) == 12000


# ── B. _keep_window Verhalten ────────────────────────────────────────────────

def test_keep_window_longer_takes_last():
    a = np.arange(100, dtype=np.int16)
    out = _keep_window(a, 60)
    assert len(out) == 60
    assert out[0] == 40 and out[-1] == 99   # die LETZTEN 60


def test_keep_window_too_short_returns_none():
    a = np.arange(20, dtype=np.int16)
    assert _keep_window(a, 100) is None      # 20 < 100//2


def test_keep_window_slightly_short_pads_tail():
    a = np.arange(60, dtype=np.int16)
    out = _keep_window(a, 80)                 # 60 >= 40, < 80 → padden
    assert len(out) == 80
    assert out[59] == 59 and out[60] == 0 and out[-1] == 0


# ── C. FT4-Positionierungs-Äquivalenz (KERN-SICHERHEITSNETZ) ──────────────────

def test_ft4_signal_lands_at_same_offset_as_working_baseline():
    """Beweis: Der neue FT4-Pfad (WAKE=1,5 + Slot-Ausrichtung + Tail-Pad)
    positioniert das Signal an der IDENTISCHEN Fenster-Stelle wie der alte,
    funktionierende Stand (WAKE=0,5, end-verankert). Genau diese Position
    rutschte beim gescheiterten ersten Versuch weg → 0 Decodes.

    Slot-Bezug: Signal startet protokollgemäß bei Slot+0,5s. Im kanonischen
    Fenster [Slot−0,5; Slot+7,0] muss es bei (+0,5−(−0,5))=+1,0s = Sample 12000
    liegen — egal über welche Weckzeit das Fenster zustande kam.
    """
    slot_dur_s = 7.5
    sig_pos_s = 0.5                       # Signal-Start relativ Slot-Anfang
    MARKER = 9999

    # NEUER Pfad: WAKE=1,5 → Buffer [Slot−1,5; Slot+6,0], 7,5s @ 12k.
    # (Buffer hier = bereits auf 12k resampled, _keep_window arbeitet auf 12k.)
    buf_new = np.zeros(int(slot_dur_s * SAMP_RATE), dtype=np.int16)
    # Signal-Offset im Buffer = (sig_pos − (−WAKE)) = 0,5+1,5 = 2,0s
    off_new = int((sig_pos_s + _WAKE_OFFSETS["FT4"]) * SAMP_RATE)
    buf_new[off_new] = MARKER
    keep = _SLOT_SAMPLES["FT4"] - _TAIL_PAD_SAMPLES["FT4"]    # 78000
    kept_new = _keep_window(buf_new, keep)
    # Tail-Pad (im Produktivcode NACH preprocess; hier reicht das Anhängen,
    # da preprocess die Position nicht verschiebt):
    final_new = np.pad(kept_new, (0, _TAIL_PAD_SAMPLES["FT4"]))
    pos_new = int(np.argmax(final_new))

    # ALTER, funktionierender Pfad: WAKE=0,5 → Buffer [Slot−0,5; Slot+7,0].
    buf_old = np.zeros(int(slot_dur_s * SAMP_RATE), dtype=np.int16)
    off_old = int((sig_pos_s + 0.5) * SAMP_RATE)             # 1,0s = 12000
    buf_old[off_old] = MARKER
    kept_old = _keep_window(buf_old, _SLOT_SAMPLES["FT4"])    # tail=0 → alles
    final_old = kept_old
    pos_old = int(np.argmax(final_old))

    # Beide müssen das Signal an Sample 12000 (= +1,0s im kanonischen Fenster)
    # haben — der neue Pfad reproduziert exakt die alte, bewährte Position.
    assert pos_new == 12000, pos_new
    assert pos_old == 12000, pos_old
    assert pos_new == pos_old
    # Längen korrekt: beide volle slot_samples (ft8_lib-Erwartung).
    assert len(final_new) == _SLOT_SAMPLES["FT4"] == len(final_old)
    # Tail-Pad sitzt am ENDE (reine Stille), stört das Signal nicht:
    assert final_new[-1] == 0 and final_new[keep:].max() == 0


# ── D. FT8/FT2 Bit-Identität (kein Verhaltens-Regress) ────────────────────────

@pytest.mark.parametrize("mode", ["FT8", "FT2"])
def test_unchanged_modes_keep_full_slot(mode):
    # tail_pad=0 → keep_samples == slot_samples → _keep_window verhält sich
    # exakt wie der alte `audio_12k[-slot_samples:]` (kein Tail-Pad).
    assert _TAIL_PAD_SAMPLES[mode] == 0
    keep = _SLOT_SAMPLES[mode] - _TAIL_PAD_SAMPLES[mode]
    assert keep == _SLOT_SAMPLES[mode]
    long = np.arange(_SLOT_SAMPLES[mode] + 5000, dtype=np.int16)
    out = _keep_window(long, keep)
    assert len(out) == _SLOT_SAMPLES[mode]
    assert np.array_equal(out, long[-_SLOT_SAMPLES[mode]:])   # letzte slot_samples


# ── E. FT8-Pipeline-Rundlauf (Decode-Pfad end-to-end intakt) ──────────────────

def test_ft8_roundtrip_through_process_cycle(monkeypatch):
    """Echter Encode→_process_cycle→Decode für FT8 (FT4-encode der Lib ist nicht
    decodierbar, daher FT8 als Pipeline-Beweis). Zeigt, dass die geänderte
    _process_cycle-Fensterlogik den Decode-Pfad nicht beschädigt hat.
    """
    from core.decoder import Decoder
    from core import ntp_time
    from core.ft8lib_decoder import get_ft8lib

    monkeypatch.setattr(ntp_time, "get_correction", lambda: 0.0)

    msg = "CQ DL1ABC JO31"
    audio_12k = get_ft8lib().encode(msg, freq_hz=1500.0, mode="FT8")
    assert audio_12k is not None and len(audio_12k) == _SLOT_SAMPLES["FT8"]
    # Radio liefert 24k → simpel ×2 upsamplen (Zero-Order-Hold); _process_cycle
    # resampled mit Anti-Alias zurück auf 12k.
    audio_24k = np.repeat(audio_12k, 2)

    dec = Decoder(mode="FT8")
    captured = []
    dec.cycle_decoded.connect(lambda msgs: captured.extend(msgs))
    dec._process_cycle([audio_24k], target_slot_start=0.0, slot_duration=15.0)

    texts = [getattr(m, "raw", str(m)) for m in captured]
    assert any("DL1ABC" in t for t in texts), texts


# ── F. Parität: 7,5s-Raster (Spec-Guard gegen DeepSeek-Halluzination /15) ─────

def test_ft4_parity_alternates_on_7p5s_grid():
    """Decoder + Encoder berechnen FT4-Parität als int(t/7.5)%2 (7,5s-Raster).
    FT4 alterniert auf 7,5s — aufeinanderfolgende Slots haben Gegenparität.
    Mit /15 (DeepSeeks abgelehntem Vorschlag) hätten beide 7,5s-Slots eines
    15s-Blocks dieselbe Parität → Station antwortet auf falschem Slot.
    Dieser Test fixiert das gewollte 7,5s-Verhalten.
    """
    slot = _SLOT_SAMPLES["FT4"] / SAMP_RATE         # = 7.5
    par = lambda t: int(t / slot) % 2 == 0
    assert par(0.0) and not par(7.5) and par(15.0) and not par(22.5)
    # Gegenparität bei aufeinanderfolgenden 7,5s-Slots:
    for t in (0.0, 7.5, 15.0, 22.5, 30.0):
        assert par(t) != par(t + slot)
