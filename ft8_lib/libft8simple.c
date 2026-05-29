/**
 * libft8simple.c -- Duenner C-Wrapper fuer kgoba/ft8_lib
 *
 * Kapselt die komplexe ft8_lib API hinter zwei einfachen Funktionen:
 *   ft8s_decode()  -- int16 Audio -> dekodierte Nachrichten
 *   ft8s_encode()  -- Nachrichtentext -> int16 Audio (15s Slot, GFSK)
 *
 * SimpleFT8 / DA1MHH -- 2026 -- MIT License (Wrapper-Code)
 * ft8_lib: MIT License (kgoba)
 */

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include <stdbool.h>

#include <ft8/decode.h>
#include <ft8/encode.h>
#include <ft8/message.h>
#include <ft8/constants.h>
#include <common/monitor.h>

/* -- Ergebnis-Struktur (Python-freundlich, fixes Layout) -- */

#define FT8S_MAX_MESSAGE  35
#define FT8S_MAX_RESULTS  200

typedef struct {
    char    message[FT8S_MAX_MESSAGE]; /* Dekodierter Text, null-terminiert    */
    float   freq_hz;                   /* Traegerfrequenz in Hz                */
    float   dt;                        /* Zeitversatz in Sekunden              */
    int     snr;                       /* SNR in dB (geschaetzt)               */
    int     ldpc_errors;               /* LDPC-Fehler (0 = perfekt)            */
} ft8s_result_t;

/* -- Callsign-Hashtable (fuer Nachrichten mit <HASH>-Calls) -- */

#define HASH_SIZE 256

static struct {
    char     callsign[13];
    uint32_t hash;
} s_hashtable[HASH_SIZE];

static int s_hashtable_count = 0;

static void hashtable_init(void) {
    s_hashtable_count = 0;
    memset(s_hashtable, 0, sizeof(s_hashtable));
}

static bool hashtable_lookup_hash(ftx_callsign_hash_type_t hash_type, uint32_t hash, char* callsign) {
    int nbits = (hash_type == FTX_CALLSIGN_HASH_22_BITS) ? 22 :
                (hash_type == FTX_CALLSIGN_HASH_12_BITS) ? 12 : 10;
    uint32_t mask = (1u << nbits) - 1u;
    for (int i = 0; i < HASH_SIZE; i++) {
        if (s_hashtable[i].callsign[0] != '\0') {
            if ((s_hashtable[i].hash & mask) == (hash & mask)) {
                strncpy(callsign, s_hashtable[i].callsign, 11);
                callsign[11] = '\0';
                return true;
            }
        }
    }
    return false;
}

static void hashtable_save(const char* callsign, uint32_t n22) {
    for (int i = 0; i < HASH_SIZE; i++) {
        if (strcmp(s_hashtable[i].callsign, callsign) == 0) return;
    }
    int slot = s_hashtable_count % HASH_SIZE;
    strncpy(s_hashtable[slot].callsign, callsign, 11);
    s_hashtable[slot].callsign[11] = '\0';
    s_hashtable[slot].hash = n22;
    if (s_hashtable_count < HASH_SIZE) s_hashtable_count++;
}

static ftx_callsign_hash_interface_t s_hash_if = {
    .lookup_hash = hashtable_lookup_hash,
    .save_hash   = hashtable_save,
};

/* ============================================================
 * ft8s_decode()
 *
 * Dekodiert einen 15s FT8-Slot aus int16-Audio.
 *
 * Parameter:
 *   samples      -- int16 PCM-Daten, MUSS 12000 Hz sein
 *   n_samples    -- Anzahl Samples (typisch 180000 fuer 15s @ 12kHz)
 *   max_freq_hz  -- Maximale Dekodierfrequenz (z.B. 3000)
 *   num_passes   -- Signal-Subtraction-Passes (1..7, empfohlen: 5)
 *   results      -- Ausgabe-Array (caller alloziert)
 *   max_results  -- Maximale Anzahl zurueckgegebener Nachrichten
 *
 * Rueckgabe: Anzahl dekodierter Nachrichten
 * ============================================================ */
int ft8s_decode(
    const int16_t* samples,
    int            n_samples,
    float          max_freq_hz,
    int            num_passes,
    ft8s_result_t* results,
    int            max_results
) {
    if (!samples || n_samples < 1 || !results || max_results < 1) return 0;

    const int sample_rate      = 12000;
    const int kMax_candidates  = 140;
    const int kLDPC_iterations = 50;
    /* P150 (v0.98.32, 27.05.2026): 10 -> 4 fuer -24 dB DX-Empfindlichkeit.
     * FT4/FT2 (Z. 369/513) bleiben bei 10 — Costas-Pattern-Laengen
     * unterschiedlich, Score-Skala nicht 1:1 (R1-V4-pro O1 ORANGE-Catch). */
    const int kMin_score       = 4;
    const int kTime_osr        = 2;
    const int kFreq_osr        = 2;

    /* Monitor initialisieren -- erzeugt Waterfall aus Audio */
    monitor_config_t mon_cfg = {
        .f_min       = 100.0f,
        .f_max       = max_freq_hz,
        .sample_rate = sample_rate,
        .time_osr    = kTime_osr,
        .freq_osr    = kFreq_osr,
        .protocol    = FTX_PROTOCOL_FT8,
    };
    monitor_t mon;
    monitor_init(&mon, &mon_cfg);
    monitor_reset(&mon);

    /* Audio in Float konvertieren und blockweise in Monitor einspeisen.
     * WICHTIG: monitor_process() erwartet block_size Samples pro Aufruf
     * (= 1 FT8-Symbol = 1920 @ 12kHz). Intern verarbeitet es time_osr
     * Subblock-Shifts -- NICHT subblock_size uebergeben! */
    int block_size = mon.block_size;   /* 1920 Samples @ 12kHz */

    float* fbuf = (float*)malloc(block_size * sizeof(float));
    if (!fbuf) { monitor_free(&mon); return 0; }

    int n_fed = 0;
    while (n_fed + block_size <= n_samples) {
        for (int i = 0; i < block_size; i++)
            fbuf[i] = (float)samples[n_fed + i] / 32768.0f;
        monitor_process(&mon, fbuf);
        n_fed += block_size;
    }
    free(fbuf);

    /* Kandidaten-Heap */
    ftx_candidate_t* heap = (ftx_candidate_t*)calloc(kMax_candidates, sizeof(ftx_candidate_t));
    if (!heap) { monitor_free(&mon); return 0; }

    int total_found = 0;
    char seen_msgs[FT8S_MAX_RESULTS][FT8S_MAX_MESSAGE];
    int  n_seen = 0;

    /* -- Multi-Pass Signal-Subtraction -- */
    for (int pass = 0; pass < num_passes && total_found < max_results; pass++) {

        int n_cands = ftx_find_candidates(&mon.wf, kMax_candidates, heap, kMin_score);
        if (n_cands == 0) break;

        bool found_new = false;

        for (int ci = 0; ci < n_cands && total_found < max_results; ci++) {
            ftx_message_t       msg;
            ftx_decode_status_t status;

            bool ok = ftx_decode_candidate(
                &mon.wf, &heap[ci], kLDPC_iterations, &msg, &status
            );
            if (!ok) continue;

            /* Nachricht in Text umwandeln.
             * WICHTIG: offsets darf nicht NULL sein -- ftx_message_decode
             * schreibt immer in offsets->types und offsets->offsets! */
            char text[FT8S_MAX_MESSAGE];
            ftx_message_offsets_t offsets;
            ftx_message_rc_t rc = ftx_message_decode(
                &msg, &s_hash_if, text, &offsets
            );
            if (rc != FTX_MESSAGE_RC_OK) continue;

            /* Duplikat-Check */
            bool dup = false;
            for (int si = 0; si < n_seen; si++) {
                if (strcmp(seen_msgs[si], text) == 0) { dup = true; break; }
            }
            if (dup) continue;

            /* Ergebnis speichern */
            strncpy(results[total_found].message, text, FT8S_MAX_MESSAGE - 1);
            results[total_found].message[FT8S_MAX_MESSAGE - 1] = '\0';

            float freq_hz = (heap[ci].freq_offset + (float)heap[ci].freq_sub / kFreq_osr)
                            * (float)sample_rate / (float)(mon.block_size * kFreq_osr);
            results[total_found].freq_hz    = freq_hz;
            results[total_found].dt         = (heap[ci].time_offset + (float)heap[ci].time_sub / kTime_osr)
                                              * FT8_SYMBOL_PERIOD;
            results[total_found].snr        = (int)(heap[ci].score / 2 - 30);
            results[total_found].ldpc_errors = status.ldpc_errors;

            if (n_seen < FT8S_MAX_RESULTS)
                strncpy(seen_msgs[n_seen++], text, FT8S_MAX_MESSAGE - 1);

            total_found++;
            found_new = true;
        }

        if (!found_new) break;

        /* TODO: Signal-Subtraction fuer Pass 2+ */
    }

    free(heap);
    monitor_free(&mon);
    return total_found;
}

/* ============================================================
 * GFSK-Synthese (phasenkontinuierliche FSK mit Gauss-Filter)
 * Uebernommen aus ft8_lib/demo/gen_ft8.c (MIT License, kgoba)
 * ============================================================ */

#define GFSK_CONST_K   5.336446f   /* == pi * sqrt(2 / log(2)) */
#define FT8_SYMBOL_BT  2.0f        /* Symbol smoothing bandwidth factor */

static void gfsk_pulse(int n_spsym, float symbol_bt, float* pulse) {
    for (int i = 0; i < 3 * n_spsym; ++i) {
        float t    = i / (float)n_spsym - 1.5f;
        float arg1 = GFSK_CONST_K * symbol_bt * (t + 0.5f);
        float arg2 = GFSK_CONST_K * symbol_bt * (t - 0.5f);
        pulse[i]   = (erff(arg1) - erff(arg2)) / 2.0f;
    }
}

static void synth_gfsk(const uint8_t* symbols, int n_sym,
                        float f0, float symbol_bt,
                        float symbol_period, int signal_rate,
                        float* signal) {
    int   n_spsym   = (int)(0.5f + signal_rate * symbol_period);
    int   n_wave    = n_sym * n_spsym;
    float hmod      = 1.0f;
    float dphi_peak = 2.0f * (float)M_PI * hmod / n_spsym;

    float* dphi  = (float*)malloc((n_wave + 2 * n_spsym) * sizeof(float));
    float* pulse = (float*)malloc(3 * n_spsym * sizeof(float));
    if (!dphi || !pulse) { free(dphi); free(pulse); return; }

    /* Basis-Frequenz */
    for (int i = 0; i < n_wave + 2 * n_spsym; ++i)
        dphi[i] = 2.0f * (float)M_PI * f0 / signal_rate;

    gfsk_pulse(n_spsym, symbol_bt, pulse);

    /* Phasenverlauf aufbauen */
    for (int i = 0; i < n_sym; ++i) {
        int ib = i * n_spsym;
        for (int j = 0; j < 3 * n_spsym; ++j)
            dphi[j + ib] += dphi_peak * symbols[i] * pulse[j];
    }
    /* Dummy-Symbole am Anfang + Ende */
    for (int j = 0; j < 2 * n_spsym; ++j) {
        dphi[j]                   += dphi_peak * pulse[j + n_spsym] * symbols[0];
        dphi[j + n_sym * n_spsym] += dphi_peak * pulse[j]           * symbols[n_sym - 1];
    }

    /* Phase integrieren -> Signal */
    float phi = 0.0f;
    for (int k = 0; k < n_wave; ++k) {
        signal[k] = sinf(phi);
        phi = fmodf(phi + dphi[k + n_spsym], 2.0f * (float)M_PI);
    }

    /* Hullkurven-Shaping (1/8 Symbol ramp) */
    int n_ramp = n_spsym / 8;
    for (int i = 0; i < n_ramp; ++i) {
        float env = (1.0f - cosf(2.0f * (float)M_PI * i / (2 * n_ramp))) / 2.0f;
        signal[i]              *= env;
        signal[n_wave - 1 - i] *= env;
    }

    free(pulse);
    free(dphi);
}

/* ============================================================
 * ft8s_encode()
 *
 * Enkodiert eine FT8-Nachricht zu int16-Audio (15s Slot @ 12kHz).
 *
 * Parameter:
 *   message_text -- z.B. "DA1TST DA1MHH -06" (null-terminiert)
 *   freq_hz      -- Traegerfrequenz in Hz (z.B. 1000.0)
 *   out_samples  -- Ausgabe-Puffer (mind. 180000 int16)
 *   max_samples  -- Groesse des Ausgabepuffers
 *
 * Rueckgabe: Anzahl Samples (= 180000 = 15s @ 12kHz), oder -1 bei Fehler
 * ============================================================ */
int ft8s_encode(
    const char* message_text,
    float       freq_hz,
    int16_t*    out_samples,
    int         max_samples
) {
    if (!message_text || !out_samples || max_samples < 1) return -1;

    const int   sample_rate = 12000;

    /* Nachricht enkodieren (Text -> 77-Bit Payload) */
    ftx_message_t msg;
    ftx_message_rc_t rc = ftx_message_encode(&msg, &s_hash_if, message_text);
    if (rc != FTX_MESSAGE_RC_OK) {
        fprintf(stderr, "[ft8s_encode] Fehler: '%s' rc=%d\n", message_text, rc);
        return -1;
    }

    /* Payload -> 79 FT8-Toene */
    uint8_t tones[FT8_NN];
    ft8_encode(msg.payload, tones);

    /* Laengen berechnen (mit Stille-Padding auf 15s) */
    int num_samples = (int)(0.5f + FT8_NN * FT8_SYMBOL_PERIOD * sample_rate); /* 151680 */
    int num_silence = (int)((FT8_SLOT_TIME * sample_rate - num_samples) / 2);  /* ~14160 */
    int total       = num_silence + num_samples + num_silence;                  /* ~180000 */

    if (total > max_samples) {
        fprintf(stderr, "[ft8s_encode] Puffer zu klein: %d < %d\n", max_samples, total);
        return -1;
    }

    /* Ausgabe mit Stille initialisieren */
    memset(out_samples, 0, total * sizeof(int16_t));

    /* GFSK-Signal erzeugen */
    float* signal = (float*)malloc(num_samples * sizeof(float));
    if (!signal) return -1;

    synth_gfsk(tones, FT8_NN, freq_hz, FT8_SYMBOL_BT, FT8_SYMBOL_PERIOD,
               sample_rate, signal);

    /* Float -> int16 (mit Stille-Offset) */
    for (int i = 0; i < num_samples; i++)
        out_samples[num_silence + i] = (int16_t)(signal[i] * 28000.0f);

    free(signal);
    return total;
}

/* ============================================================
 * ft8s_decode_ft4()
 *
 * Dekodiert einen 7.5s FT4-Slot aus int16-Audio.
 * Gleiche Signatur wie ft8s_decode(), nur FT4-Protokoll.
 * ============================================================ */
int ft8s_decode_ft4(
    const int16_t* samples,
    int            n_samples,
    float          max_freq_hz,
    int            num_passes,
    ft8s_result_t* results,
    int            max_results
) {
    if (!samples || n_samples < 1 || !results || max_results < 1) return 0;

    const int sample_rate      = 12000;
    const int kMax_candidates  = 140;
    const int kLDPC_iterations = 50;
    const int kMin_score       = 10;
    const int kTime_osr        = 2;
    const int kFreq_osr        = 2;

    monitor_config_t mon_cfg = {
        .f_min       = 100.0f,
        .f_max       = max_freq_hz,
        .sample_rate = sample_rate,
        .time_osr    = kTime_osr,
        .freq_osr    = kFreq_osr,
        .protocol    = FTX_PROTOCOL_FT4,  /* ← FT4 statt FT8! */
    };
    monitor_t mon;
    monitor_init(&mon, &mon_cfg);
    monitor_reset(&mon);

    int block_size = mon.block_size;   /* 576 Samples @ 12kHz (FT4 Symbol) */

    float* fbuf = (float*)malloc(block_size * sizeof(float));
    if (!fbuf) { monitor_free(&mon); return 0; }

    int n_fed = 0;
    while (n_fed + block_size <= n_samples) {
        for (int i = 0; i < block_size; i++)
            fbuf[i] = (float)samples[n_fed + i] / 32768.0f;
        monitor_process(&mon, fbuf);
        n_fed += block_size;
    }
    free(fbuf);

    ftx_candidate_t* heap = (ftx_candidate_t*)calloc(kMax_candidates, sizeof(ftx_candidate_t));
    if (!heap) { monitor_free(&mon); return 0; }

    int total_found = 0;
    char seen_msgs[FT8S_MAX_RESULTS][FT8S_MAX_MESSAGE];
    int  n_seen = 0;

    for (int pass = 0; pass < num_passes && total_found < max_results; pass++) {
        int n_cands = ftx_find_candidates(&mon.wf, kMax_candidates, heap, kMin_score);
        if (n_cands == 0) break;

        bool found_new = false;
        for (int ci = 0; ci < n_cands && total_found < max_results; ci++) {
            ftx_message_t       msg;
            ftx_decode_status_t status;
            bool ok = ftx_decode_candidate(&mon.wf, &heap[ci], kLDPC_iterations, &msg, &status);
            if (!ok) continue;

            char text[FT8S_MAX_MESSAGE];
            ftx_message_offsets_t offsets;
            ftx_message_rc_t rc = ftx_message_decode(&msg, &s_hash_if, text, &offsets);
            if (rc != FTX_MESSAGE_RC_OK) continue;

            bool dup = false;
            for (int si = 0; si < n_seen; si++) {
                if (strcmp(seen_msgs[si], text) == 0) { dup = true; break; }
            }
            if (dup) continue;

            strncpy(results[total_found].message, text, FT8S_MAX_MESSAGE - 1);
            results[total_found].message[FT8S_MAX_MESSAGE - 1] = '\0';
            float freq_hz = (heap[ci].freq_offset + (float)heap[ci].freq_sub / kFreq_osr)
                            * (float)sample_rate / (float)(mon.block_size * kFreq_osr);
            results[total_found].freq_hz    = freq_hz;
            results[total_found].dt         = (heap[ci].time_offset + (float)heap[ci].time_sub / kTime_osr)
                                              * FT4_SYMBOL_PERIOD;
            results[total_found].snr        = (int)(heap[ci].score / 2 - 30);
            results[total_found].ldpc_errors = status.ldpc_errors;

            if (n_seen < FT8S_MAX_RESULTS)
                strncpy(seen_msgs[n_seen++], text, FT8S_MAX_MESSAGE - 1);
            total_found++;
            found_new = true;
        }
        if (!found_new) break;
    }

    free(heap);
    monitor_free(&mon);
    return total_found;
}

/* ============================================================
 * ft8s_encode_ft4()
 *
 * Enkodiert eine FT4-Nachricht zu int16-Audio (7.5s Slot @ 12kHz).
 * ============================================================ */
int ft8s_encode_ft4(
    const char* message_text,
    float       freq_hz,
    int16_t*    out_samples,
    int         max_samples
) {
    if (!message_text || !out_samples || max_samples < 1) return -1;

    const int sample_rate = 12000;

    ftx_message_t msg;
    ftx_message_rc_t rc = ftx_message_encode(&msg, &s_hash_if, message_text);
    if (rc != FTX_MESSAGE_RC_OK) return -1;

    uint8_t tones[FT4_NN];
    ft4_encode(msg.payload, tones);

    int num_samples = (int)(0.5f + FT4_NN * FT4_SYMBOL_PERIOD * sample_rate);
    int num_silence = (int)((FT4_SLOT_TIME * sample_rate - num_samples) / 2);
    int total       = num_silence + num_samples + num_silence;

    if (total > max_samples) return -1;

    memset(out_samples, 0, total * sizeof(int16_t));

    float* signal = (float*)malloc(num_samples * sizeof(float));
    if (!signal) return -1;

    synth_gfsk(tones, FT4_NN, freq_hz, FT8_SYMBOL_BT, FT4_SYMBOL_PERIOD,
               sample_rate, signal);

    for (int i = 0; i < num_samples; i++)
        out_samples[num_silence + i] = (int16_t)(signal[i] * 28000.0f);

    free(signal);
    return total;
}

/* ============================================================
 * ft8s_decode_ft2()
 *
 * FT2 = FT4 mit halber Symbol-Rate (288 sps statt 576 @ 12kHz).
 * Nativ: FTX_PROTOCOL_FT2 bei 12kHz (kein Resample noetig!).
 * ============================================================ */
int ft8s_decode_ft2(
    const int16_t* samples,
    int            n_samples,
    float          max_freq_hz,
    int            num_passes,
    ft8s_result_t* results,
    int            max_results
) {
    if (!samples || n_samples < 1 || !results || max_results < 1) return 0;

    const int sample_rate      = 12000;  /* Native Rate, kein Resample! */
    const int kMax_candidates  = 140;
    const int kLDPC_iterations = 50;
    const int kMin_score       = 10;
    const int kTime_osr        = 2;
    const int kFreq_osr        = 2;

    monitor_config_t mon_cfg = {
        .f_min       = 100.0f,
        .f_max       = max_freq_hz,
        .sample_rate = sample_rate,
        .time_osr    = kTime_osr,
        .freq_osr    = kFreq_osr,
        .protocol    = FTX_PROTOCOL_FT2,   /* Nativer FT2 Protokoll-Typ! */
    };
    monitor_t mon;
    monitor_init(&mon, &mon_cfg);
    monitor_reset(&mon);

    int block_size = mon.block_size;   /* 288 Samples @ 12kHz (FT2 Symbol) */
    float* fbuf = (float*)malloc(block_size * sizeof(float));
    if (!fbuf) { monitor_free(&mon); return 0; }

    int n_fed = 0;
    while (n_fed + block_size <= n_samples) {
        for (int i = 0; i < block_size; i++)
            fbuf[i] = (float)samples[n_fed + i] / 32768.0f;
        monitor_process(&mon, fbuf);
        n_fed += block_size;
    }
    free(fbuf);

    ftx_candidate_t* heap = (ftx_candidate_t*)calloc(kMax_candidates, sizeof(ftx_candidate_t));
    if (!heap) { monitor_free(&mon); return 0; }

    int total_found = 0;
    char seen_msgs[FT8S_MAX_RESULTS][FT8S_MAX_MESSAGE];
    int  n_seen = 0;

    for (int pass = 0; pass < num_passes && total_found < max_results; pass++) {
        int n_cands = ftx_find_candidates(&mon.wf, kMax_candidates, heap, kMin_score);
        if (n_cands == 0) break;

        bool found_new = false;
        for (int ci = 0; ci < n_cands && total_found < max_results; ci++) {
            ftx_message_t       msg;
            ftx_decode_status_t status;
            bool ok = ftx_decode_candidate(&mon.wf, &heap[ci], kLDPC_iterations, &msg, &status);
            if (!ok) continue;

            char text[FT8S_MAX_MESSAGE];
            ftx_message_offsets_t offsets;
            ftx_message_rc_t rc = ftx_message_decode(&msg, &s_hash_if, text, &offsets);
            if (rc != FTX_MESSAGE_RC_OK) continue;

            bool dup = false;
            for (int si = 0; si < n_seen; si++) {
                if (strcmp(seen_msgs[si], text) == 0) { dup = true; break; }
            }
            if (dup) continue;

            strncpy(results[total_found].message, text, FT8S_MAX_MESSAGE - 1);
            results[total_found].message[FT8S_MAX_MESSAGE - 1] = '\0';
            float freq_hz = (heap[ci].freq_offset + (float)heap[ci].freq_sub / kFreq_osr)
                            * (float)sample_rate / (float)(mon.block_size * kFreq_osr);
            results[total_found].freq_hz    = freq_hz;
            results[total_found].dt         = (heap[ci].time_offset + (float)heap[ci].time_sub / kTime_osr)
                                              * FT2_SYMBOL_PERIOD;  /* 0.024s pro Symbol */
            results[total_found].snr        = (int)(heap[ci].score / 2 - 30);
            results[total_found].ldpc_errors = status.ldpc_errors;

            if (n_seen < FT8S_MAX_RESULTS)
                strncpy(seen_msgs[n_seen++], text, FT8S_MAX_MESSAGE - 1);
            total_found++;
            found_new = true;
        }
        if (!found_new) break;
    }

    free(heap);
    monitor_free(&mon);
    return total_found;
}

/* ============================================================
 * ft8s_encode_ft2()
 *
 * FT2 Encoding: FT4-Toene bei doppelter Symbol-Rate.
 * ============================================================ */
int ft8s_encode_ft2(
    const char* message_text,
    float       freq_hz,
    int16_t*    out_samples,
    int         max_samples
) {
    if (!message_text || !out_samples || max_samples < 1) return -1;

    const int   sample_rate = 12000;
    const float symbol_period = FT2_SYMBOL_PERIOD;   /* 0.024s (288 sps @ 12kHz) */
    const float slot_time = FT2_SLOT_TIME;

    ftx_message_t msg;
    ftx_message_rc_t rc = ftx_message_encode(&msg, &s_hash_if, message_text);
    if (rc != FTX_MESSAGE_RC_OK) return -1;

    /* FT4 Toene (gleiche Symbolstruktur) */
    uint8_t tones[FT4_NN];
    ft4_encode(msg.payload, tones);

    int num_samples = (int)(0.5f + FT4_NN * symbol_period * sample_rate); /* 103×288=29664 */
    int num_silence = (int)((slot_time * sample_rate - num_samples) / 2);
    int total       = num_silence + num_samples + num_silence;

    if (total > max_samples) return -1;
    memset(out_samples, 0, total * sizeof(int16_t));

    float* signal = (float*)malloc(num_samples * sizeof(float));
    if (!signal) return -1;

    synth_gfsk(tones, FT4_NN, freq_hz, FT8_SYMBOL_BT, symbol_period,
               sample_rate, signal);

    for (int i = 0; i < num_samples; i++)
        out_samples[num_silence + i] = (int16_t)(signal[i] * 28000.0f);

    free(signal);
    return total;
}

/* -- Hilfsfunktion: Groesse der Ergebnis-Struktur (fuer ctypes) -- */
int ft8s_result_size(void) {
    return (int)sizeof(ft8s_result_t);
}
