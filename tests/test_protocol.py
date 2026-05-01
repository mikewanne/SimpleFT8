"""Tests fuer core/protocol.py — FT8/FT4/FT2 Protokoll-Konstanten und Properties.

Prueft:
- symbol_duration / signal_duration / waveform_samples fuer alle 3 Profile
- signal_duration < slot_time (Protokoll-Overhead)
- get_profile() Case-Insensitivity + Unknown-Fallback
- BAND_FREQUENCIES Vollstaendigkeit
- Frozen Dataclass (Immutabilitaet)
"""

import pytest
from core.protocol import FT8, FT4, FT2, PROFILES, get_profile, BAND_FREQUENCIES


# ── Parametrisierte Mathematik-Tests ─────────────────────────────────────────

@pytest.mark.parametrize("profile, exp_sym_dur, exp_sig_dur, exp_wave", [
    (FT8, 1920 / 12000,  79 * (1920 / 12000),  79 * 1920),   # 0.16s, 12.64s, 151680
    (FT4,  576 / 12000, 103 * ( 576 / 12000), 103 *  576),   # 0.048s, 4.944s, 59328
    (FT2,  288 / 12000, 103 * ( 288 / 12000), 103 *  288),   # 0.024s, 2.472s, 29664
])
def test_protocol_math(profile, exp_sym_dur, exp_sig_dur, exp_wave):
    """symbol_duration / signal_duration / waveform_samples stimmen fuer alle Profile."""
    assert abs(profile.symbol_duration - exp_sym_dur) < 1e-9, (
        f"{profile.name}: symbol_duration {profile.symbol_duration} != {exp_sym_dur}"
    )
    assert abs(profile.signal_duration - exp_sig_dur) < 1e-9, (
        f"{profile.name}: signal_duration {profile.signal_duration} != {exp_sig_dur}"
    )
    assert profile.waveform_samples == exp_wave, (
        f"{profile.name}: waveform_samples {profile.waveform_samples} != {exp_wave}"
    )


@pytest.mark.parametrize("profile", [FT8, FT4, FT2])
def test_signal_shorter_than_slot(profile):
    """signal_duration < slot_time — Pause fuer Protokoll-Overhead vorhanden."""
    assert profile.signal_duration < profile.slot_time, (
        f"{profile.name}: signal_duration {profile.signal_duration:.3f}s >= "
        f"slot_time {profile.slot_time}s"
    )


@pytest.mark.parametrize("profile", [FT8, FT4, FT2])
def test_sample_rate_constant(profile):
    """Alle Profile nutzen 12 kHz Basis-Samplerate."""
    assert profile.sample_rate == 12000


@pytest.mark.parametrize("profile", [FT8, FT4, FT2])
def test_ldpc_constants(profile):
    """LDPC 174/91 ist fuer alle Profile gleich."""
    assert profile.bits == 77
    assert profile.ldpc_n == 174
    assert profile.ldpc_k == 91


# ── get_profile() ─────────────────────────────────────────────────────────────

def test_get_profile_case_insensitive():
    """get_profile() akzeptiert Gross- und Kleinschreibung."""
    assert get_profile("FT8") is FT8
    assert get_profile("ft8") is FT8
    assert get_profile("Ft8") is FT8
    assert get_profile("FT4") is FT4
    assert get_profile("ft4") is FT4
    assert get_profile("FT2") is FT2


def test_get_profile_unknown_returns_ft8():
    """Unbekannter Modus faellt auf FT8 zurueck (sicherer Default)."""
    assert get_profile("UNKNOWN") is FT8
    assert get_profile("") is FT8
    assert get_profile("FT9") is FT8


def test_profiles_dict_complete():
    """PROFILES-Dict enthaelt alle 3 Modi."""
    assert set(PROFILES.keys()) == {"FT8", "FT4", "FT2"}
    assert PROFILES["FT8"] is FT8
    assert PROFILES["FT4"] is FT4
    assert PROFILES["FT2"] is FT2


# ── BAND_FREQUENCIES ─────────────────────────────────────────────────────────

def test_ft8_has_key_bands():
    """FT8 hat alle wichtigen Baender von 160m bis 10m."""
    expected = {"160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"}
    assert expected.issubset(set(BAND_FREQUENCIES["FT8"].keys()))


def test_ft4_no_160m():
    """FT4 hat kein 160m-Band (protokollkorrekt)."""
    assert "160m" not in BAND_FREQUENCIES["FT4"]


def test_ft2_no_160m():
    """FT2 hat kein 160m-Band (protokollkorrekt)."""
    assert "160m" not in BAND_FREQUENCIES["FT2"]


def test_band_frequencies_are_mhz():
    """Alle Dial-Frequenzen liegen im Amateur-MHz-Bereich (1-30 MHz)."""
    for mode, bands in BAND_FREQUENCIES.items():
        for band, freq in bands.items():
            assert 1.0 <= freq <= 30.0, (
                f"{mode}/{band}: Frequenz {freq} MHz ausserhalb 1-30 MHz"
            )


# ── Frozen Dataclass (Immutabilitaet) ────────────────────────────────────────

def test_protocol_is_frozen():
    """ProtocolProfile ist immutabel — Aenderung wirft FrozenInstanceError."""
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        FT8.slot_time = 99.0
    with pytest.raises(FrozenInstanceError):
        setattr(FT8, "slot_time", 99.0)


# ── Konsistenz-Check ──────────────────────────────────────────────────────────

def test_ft4_ft2_same_symbol_count():
    """FT4 und FT2 haben die gleiche Anzahl Symbole (103) — nur Timing unterscheidet sich."""
    assert FT4.num_symbols == FT2.num_symbols == 103
    assert FT4.num_data == FT2.num_data == 87
    assert FT4.num_sync == FT2.num_sync == 16


def test_ft8_different_symbol_count():
    """FT8 hat 79 Symbole (Costas-Sync) — anders als FT4/FT2."""
    assert FT8.num_symbols == 79
    assert FT8.num_sync == 21  # 3x Costas-7
