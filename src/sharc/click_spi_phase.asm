// METRO-TAPSYNC-R02B3-BPM-RELOCK-DSPMETER: BPM-stable TAP phase and accents.
// click_spi_phase.asm - the Metronome block's kernel: a short tone burst on every beat, added to
// the block's input. A primitive of the stock HX Stomp 3.80 firmware, called once per
// 16-sample block with I0 the instance's DM block, I1 the input and I2 the output.
//
// Knobs (the generic store puts pid p in DM(p, I0)):
//   DM(5)  the beat in seconds (Time; the parameter map's tempo sync gives it from the BPM)
//   DM(6)  Level in dB
//   DM(7)  Accent: beats to a bar, 1 = no accent
//   DM(8)  Thru: not 0 passes the input
// The rest of the instance's 145 words is its state, 0 when the block is created. Beats are
// counted in samples from the last one, so each click starts on its sample, and a new Time
// puts the next beat a new beat after the last (at once if that has passed).
// The 41C quarter-note case is explicitly targeted: M4 LED ON edges drive click
// phase. On 41C metronome re-enable, reset bar phase and wait for the next TAP
// pulse for an accented beat (no off-grid double click). When no fresh TAP arrives
// for two Time intervals, fall back to a local sample-based beat. Any invalid
// SPI buffer snapshot (incorrect marker or XOR complement) is ignored. This
// kernel adds no M4 API calls, and retains the 16-sample SHARC audio block size.
// Note subdivisions other than 1/4 are outside this version's phase contract.
// On first creation with a valid SPI frame, wait for the next TAP LED pulse;
// on standalone startup with no valid frame, retain the original first click.
// R02B3: preserve the previous TAP period across tempo changes: a faster
// BPM cannot manufacture a stale-event timeout, phantom click, or displaced
// accent. Isolated invalid SPI frames never bypass the external-phase guard.
// A genuine two-beat TAP dropout may fall back to the local clock, but the
// first returning TAP event resets the bar to an accented downbeat.

.equ C_SINCE,  20                       // samples since the last beat
.equ C_MET,    26                       // nonzero after the first call
.equ C_CLK_LAST, 27                  // EMUCLK at the previous call, if any
.equ C_SPI_SEEN,   28                  // has at least one valid M4 SPI event frame arrived
.equ C_SPI_TAP,    29                  // last acknowledged M4 TAP LED rising-edge counter
.equ C_SPI_ENABLE, 30                  // last acknowledged 41C metronome-enable counter
.equ C_SPI_MASTER, 31                  // external TAP phase active
.equ C_SPI_PENDING,32                  // one exactly-once audio click due at block start
.equ C_SPI_HOLD_PERIOD,33              // Time samples at the most recent real TAP edge
.equ SPI_MARKER,   0x4d543242          // validated R02B1 / B1E on SHARC 0xc3da6
.equ SPI_RING,     0xc3da6            // M4 SPI TX words240..243, observed in SHARC DM
.equ C_GAP,    375000                  // > 2.5 x 150k cycles, to tolerate scheduling jitter
.equ C_BEAT,   21                       // the beat in the bar, 0 the downbeat
.equ C_ENV,    22                       // the burst's envelope
.equ C_Y1,     23                       // the oscillator's last two outputs
.equ C_Y2,     24
.equ C_COEF,   25                       // its 2 cos w
.equ C_SAVE,   100                      // the caller's registers

.equ PEYEN,    0x200000
.equ BDCST9,   0x400000

.equ FS,       48000
.equ MIN_BEAT, 4800                     // 100 ms: 600 BPM
.equ MAX_BEAT, 384000                   // 8 s, Time's maximum
.equ MAX_BAR,  12

.section pm KIT_PM_BASE

CUSTOM_AMP_ENTRY:
    DM(C_SAVE + 0, I0) = MODE1;
    BIT CLR MODE1 PEYEN | BDCST9;
    DM(C_SAVE + 1, I0) = R0;
    DM(C_SAVE + 2, I0) = R1;
    DM(C_SAVE + 3, I0) = R2;
    DM(C_SAVE + 4, I0) = R3;
    DM(C_SAVE + 5, I0) = R4;
    DM(C_SAVE + 6, I0) = R5;
    DM(C_SAVE + 7, I0) = R6;
    DM(C_SAVE + 8, I0) = R7;
    DM(C_SAVE + 9, I0) = R8;
    DM(C_SAVE + 10, I0) = R9;
    DM(C_SAVE + 11, I0) = R10;
    DM(C_SAVE + 12, I0) = R11;
    DM(C_SAVE + 13, I0) = R12;
    DM(C_SAVE + 14, I0) = R13;
    DM(C_SAVE + 15, I0) = R14;
    R0 = I4;                            // (a DAG1 register cannot be stored through I0)
    DM(C_SAVE + 16, I0) = R0;
    R0 = L4;
    DM(C_SAVE + 17, I0) = R0;
    R0 = I5;
    DM(C_SAVE + 18, I0) = R0;
    R0 = L5;
    DM(C_SAVE + 19, I0) = R0;
    L4 = 0;
    L5 = 0;
    I4 = I1;
    I5 = I2;

    F8 = DM(5, I0);                     // the beat in samples, 100 ms .. 8 s
    F9 = 48000.0;
    F8 = F8 * F9;
    R12 = FIX F8;
    R9 = MIN_BEAT;
    R12 = MAX(R12, R9);
    R9 = MAX_BEAT;
    R12 = MIN(R12, R9);

    F8 = DM(6, I0);                     // Level: 0.5 x 2^(dB / 20 log2 10), 2^f by a cubic
    F9 = 0.16609640474;
    F8 = F8 * F9;
    F9 = 16.0;                          // (+16 keeps it positive for TRUNC: dB >= -96)
    F8 = F8 + F9;
    R10 = TRUNC F8;
    F11 = FLOAT R10;
    F8 = F8 - F11;
    F6 = 0.0781633;
    F6 = F6 * F8;
    F9 = 0.2261586;
    F6 = F6 + F9;
    F6 = F6 * F8;
    F9 = 0.6951786;
    F6 = F6 + F9;
    F6 = F6 * F8;
    F9 = 1.0;
    F6 = F6 + F9;
    R9 = 17;                            // -16, and -1 for the 0.5
    R10 = R10 - R9;
    F6 = SCALB F6 BY R10;

    R7 = DM(8, I0);                     // Thru
    R7 = PASS R7;
    F7 = 1.0;
    IF EQ F7 = F7 - F7;

    R14 = DM(7, I0);                    // Accent
    R9 = 1;
    R14 = MAX(R14, R9);
    R9 = MAX_BAR;
    R14 = MIN(R14, R9);

    R0 = EMUCLK;                        // retain stock callback gap tracking
    R1 = DM(C_CLK_LAST, I0);
    DM(C_CLK_LAST, I0) = R0;
    R10 = R0 - R1;                       // spare register: elapsed SHARC cycles

    // Check marker and all three current frame words. The 4-word echo was
    // independently verified in R02B1E on the physical HX Stomp.
    R1 = DM(SPI_RING);
    R5 = SPI_MARKER;
    COMP(R1, R5);
    IF NE JUMP c_spi_invalid;
    R2 = DM(SPI_RING + 1);              // current M4 TAP edge count
    R3 = DM(SPI_RING + 2);              // current M4 metronome-enable count
    R4 = DM(SPI_RING + 3);              // complemented XOR integrity check
    R5 = R1 XOR R2;
    R5 = R5 XOR R3;
    R5 = R5 XOR R4;
    R5 = R5 + 1;                        // all-ones XOR => 0 on wrapping +1
    R5 = PASS R5;
    IF NE JUMP c_spi_invalid;

    R5 = DM(C_SPI_SEEN, I0);
    R5 = PASS R5;
    IF EQ JUMP c_spi_first;
    R5 = DM(C_SPI_ENABLE, I0);
    COMP(R3, R5);
    IF NE JUMP c_spi_reenable;
    R5 = DM(C_SPI_TAP, I0);
    COMP(R2, R5);
    IF NE JUMP c_spi_beat_event;
    R0 = DM(C_SINCE, I0);             // no new M4 edge this audio block
    JUMP c_resume;

c_spi_first:
    R5 = 1;
    DM(C_SPI_SEEN, I0) = R5;
    DM(C_SPI_MASTER, I0) = R5;
    DM(C_SPI_TAP, I0) = R2;           // ignore stale TAP history on activation
    DM(C_SPI_ENABLE, I0) = R3;
    R0 = 0;                           // on initial block, wait for the next TAP
    JUMP c_reset_bar;

c_spi_reenable:
    DM(C_SPI_ENABLE, I0) = R3;
    DM(C_SPI_TAP, I0) = R2;           // discard edges during bypass
    R5 = 1;
    DM(C_SPI_MASTER, I0) = R5;
    R0 = 0;
    JUMP c_reset_bar;                 // next external TAP is accented downbeat

c_reset_bar:
    DM(C_SPI_HOLD_PERIOD, I0) = R12;   // preserve pre-edit TAP period on initial/re-enable
    R5 = 0;
    DM(C_BEAT, I0) = R5;
    DM(C_ENV, I0) = R5;
    DM(C_Y1, I0) = R5;
    DM(C_Y2, I0) = R5;
    DM(C_COEF, I0) = R5;
    DM(C_SPI_PENDING, I0) = R5;
    JUMP c_resume;

c_spi_beat_event:
    DM(C_SPI_TAP, I0) = R2;
    DM(C_SPI_HOLD_PERIOD, I0) = R12; // update only when a real TAP arrives
    // A dropout may have allowed local beats. On the first returning TAP,
    // restart the accent at the downbeat instead of preserving the old phase.
    R5 = DM(C_SPI_MASTER, I0);
    R5 = PASS R5;
    IF NE JUMP c_spi_edge_live;
    R5 = 0;
    DM(C_BEAT, I0) = R5;
    DM(C_ENV, I0) = R5;
    DM(C_Y1, I0) = R5;
    DM(C_Y2, I0) = R5;
    DM(C_COEF, I0) = R5;
c_spi_edge_live:
    R5 = 1;
    DM(C_SPI_MASTER, I0) = R5;
    DM(C_SPI_PENDING, I0) = R5;      // one precisely once-per-edge click
    R0 = DM(C_SINCE, I0);
    JUMP c_resume;

c_spi_invalid:
    // After acquiring a valid M4 TAP stream, even a single bad SPI snapshot
    // must honor the external-phase guard. On R02B2 this path fell directly
    // into the local clock and generated an offbeat when BPM changed.
    R1 = DM(C_SPI_SEEN, I0);
    R1 = PASS R1;
    IF EQ JUMP c_spi_no_stream;
    R0 = DM(C_SINCE, I0);
    JUMP c_resume;
c_spi_no_stream:
    // Retain original standalone click start when no valid transport exists.
    R1 = DM(C_MET, I0);
    R1 = PASS R1;
    IF EQ JUMP c_restart;
    BTST R10 BY 31;
    IF NOT SZ JUMP c_restart;
    R1 = C_GAP;
    COMP(R10, R1);
    IF GT JUMP c_restart;
    R0 = DM(C_SINCE, I0);
    JUMP c_resume;

c_restart:
    R0 = PASS R12;                    // stock fallback: immediate accented start
    R1 = 0;
    DM(C_BEAT, I0) = R1;
    DM(C_ENV, I0) = R1;
    DM(C_Y1, I0) = R1;
    DM(C_Y2, I0) = R1;
    DM(C_COEF, I0) = R1;
    R5 = 0;
    DM(C_SPI_MASTER, I0) = R5;
    DM(C_SPI_PENDING, I0) = R5;
c_resume:
    R1 = 1;
    DM(C_MET, I0) = R1;
    R13 = DM(C_BEAT, I0);
    F4 = DM(C_ENV, I0);
    F1 = DM(C_Y1, I0);
    F2 = DM(C_Y2, I0);
    F3 = DM(C_COEF, I0);
    F5 = 0.99653379;
    R11 = DM(C_SPI_HOLD_PERIOD, I0);
    R11 = MAX(R11, R12);              // guard against shortening Time mid-beat
    R11 = R11 + R11;                  // two periods from longest old/new tempo

    // A validated new TAP event starts the next click at the first audio
    // sample of this 16-sample block, with no local-oscillator double-click.
    R9 = DM(C_SPI_PENDING, I0);
    R9 = PASS R9;
    IF EQ JUMP c_spi_no_pending;
    R9 = 0;
    DM(C_SPI_PENDING, I0) = R9;
    CALL c_tick;
c_spi_no_pending:
    LCNTR = 16, DO c_last UNTIL LCE;
      R9 = DM(C_SPI_MASTER, I0);
      R9 = PASS R9;
      IF EQ JUMP c_spi_local;
      COMP(R0, R11);                // 2 x MAX(last real TAP period, current Time)
      IF LT JUMP c_spi_no_local_tick;
      R9 = 0;
      DM(C_SPI_MASTER, I0) = R9;     // TAP absent: recover local click timing
c_spi_local:
      COMP(R0, R12);
      IF GE CALL c_tick;
c_spi_no_local_tick:
      R0 = R0 + 1;
      F8 = F3 * F1;                     // the oscillator: y = 2 cos w y1 - y2
      F8 = F8 - F2;
      F2 = PASS F1;
      F1 = PASS F8;
      F9 = F8 * F4;
      F4 = F4 * F5;
      F9 = F9 * F6;
      F10 = DM(I4, 1);
      F10 = F10 * F7;
      F10 = F10 + F9;
c_last: DM(I5, 1) = F10;

    DM(C_SINCE, I0) = R0;
    DM(C_BEAT, I0) = R13;
    DM(C_ENV, I0) = F4;
    DM(C_Y1, I0) = F1;
    DM(C_Y2, I0) = F2;
    DM(C_COEF, I0) = F3;

    R0 = DM(C_SAVE + 16, I0);
    I4 = R0;
    R0 = DM(C_SAVE + 17, I0);
    L4 = R0;
    R0 = DM(C_SAVE + 18, I0);
    I5 = R0;
    R0 = DM(C_SAVE + 19, I0);
    L5 = R0;
    R0 = DM(C_SAVE + 1, I0);
    R1 = DM(C_SAVE + 2, I0);
    R2 = DM(C_SAVE + 3, I0);
    R3 = DM(C_SAVE + 4, I0);
    R4 = DM(C_SAVE + 5, I0);
    R5 = DM(C_SAVE + 6, I0);
    R6 = DM(C_SAVE + 7, I0);
    R7 = DM(C_SAVE + 8, I0);
    R8 = DM(C_SAVE + 9, I0);
    R9 = DM(C_SAVE + 10, I0);
    R10 = DM(C_SAVE + 11, I0);
    R11 = DM(C_SAVE + 12, I0);
    R12 = DM(C_SAVE + 13, I0);
    R13 = DM(C_SAVE + 14, I0);
    R14 = DM(C_SAVE + 15, I0);
    MODE1 = DM(C_SAVE + 0, I0);
    NOP;
    RTS (LR);                           // as NAM's kernel returns

// A beat: a burst from sin w (1 kHz, the downbeat 2 kHz).
c_tick:
    R0 = R0 - R0;
    F4 = 1.0;
    F2 = 0.0;
    F1 = 0.13052619;
    F3 = 1.98288972;
    R13 = PASS R13;
    IF NE JUMP c_next;
    R9 = 1;
    COMP(R14, R9);                      // no accent with one beat to a bar
    IF EQ JUMP c_next;
    F1 = 0.25881905;
    F3 = 1.93185165;
c_next:
    R13 = R13 + 1;
    COMP(R13, R14);
    IF GE R13 = R13 - R13;
    RTS;
