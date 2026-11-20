// click.asm - the Metronome block's kernel: a short tone burst on every beat, added to
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
// If the stock host stops calling us on bypass, a missing audio-block callback is
// detected through EMUCLK. The next callback starts an accented downbeat rather than
// resuming a stale fractional beat/bar. Whether the stock host skips the bypassed
// primitive must still be verified on hardware (RAM-run only until verified).

.equ C_SINCE,  20                       // samples since the last beat
.equ C_MET,    26                       // nonzero after the first call
.equ C_CLK_LAST, 27
.equ C_MP_LAST, 28
.equ C_MP_ACTIVE, 29
.equ C_MP_PENDING, 30                  // EMUCLK at the previous call, if any
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

    R0 = EMUCLK;                        // elapsed cycles reveal a bypassed kernel (if its calls stop)
    R1 = DM(C_CLK_LAST, I0);
    DM(C_CLK_LAST, I0) = R0;
    R0 = R0 - R1;                       // unsigned elapsed cycles modulo 2^32
    R1 = DM(C_MET, I0);
    R1 = PASS R1;
    IF EQ JUMP c_restart;               // newly created instance
    R1 = DM(KIT_MP_EVENT_ADDR);          // the latest M4 beat or re-enable event
    R2 = DM(C_MP_LAST, I0);
    COMP(R1, R2);
    IF NE JUMP c_mp_event;
    R1 = DM(C_MP_ACTIVE, I0);
    R1 = PASS R1;
    IF NE JUMP c_mp_running;           // M4 TAP, not EMUCLK gaps, owns phase

    BTST R0 BY 31;                      // elapsed cycles are a 32-bit unsigned count
    IF NOT SZ JUMP c_restart;           // BTST sets SZ (not TF) on this SHARC
    R1 = C_GAP;
    COMP(R0, R1);
    IF GT JUMP c_restart;               // multiple audio blocks missed
    R0 = DM(C_SINCE, I0);
    JUMP c_resume;
c_mp_running:
    R0 = DM(C_SINCE, I0);
    JUMP c_resume;
c_mp_event:
    DM(C_MP_LAST, I0) = R1;
    R2 = 1;
    DM(C_MP_ACTIVE, I0) = R2;
    DM(C_MP_PENDING, I0) = R2;
    R2 = 3;
    COMP(R1, R2);
    IF GE JUMP c_restart;              // bypass re-enable: restart at accented beat one
    R0 = DM(C_SINCE, I0);
    JUMP c_resume;
c_restart:
    R1 = DM(C_MET, I0);
    R1 = PASS R1;
    IF NE JUMP c_mp_existing;
    R1 = DM(KIT_MP_EVENT_ADDR);
    DM(C_MP_LAST, I0) = R1;            // ignore stale events on a new instance
c_mp_existing:
    R0 = PASS R12;                      // force an immediate click on the first sample
    R1 = 0;
    DM(C_BEAT, I0) = R1;                // downbeat at Accent = 4
    DM(C_ENV, I0) = R1;                 // discard the previous click's tail
    DM(C_Y1, I0) = R1;
    DM(C_Y2, I0) = R1;
    DM(C_COEF, I0) = R1;
c_resume:
    R1 = 1;
    DM(C_MET, I0) = R1;
    R13 = DM(C_BEAT, I0);
    F4 = DM(C_ENV, I0);
    F1 = DM(C_Y1, I0);
    F2 = DM(C_Y2, I0);
    F3 = DM(C_COEF, I0);
    F5 = 0.99653379;                    // the envelope's step: a 6 ms time constant
    R9 = DM(C_MP_PENDING, I0);
    R9 = PASS R9;
    IF EQ JUMP c_mp_no_pending;
    R9 = 0;
    DM(C_MP_PENDING, I0) = R9;
    CALL c_tick;                        // next DSP callback starts the TAP/enable click
c_mp_no_pending:
    LCNTR = 16, DO c_last UNTIL LCE;
      R9 = DM(C_MP_ACTIVE, I0);
      R9 = PASS R9;
      IF EQ JUMP c_mp_unlocked;
      R9 = R12 + R12;
      COMP(R0, R9);
      IF LT JUMP c_mp_no_tick;         // avoid double-clicks before the next TAP pulse
      R9 = 0;
      DM(C_MP_ACTIVE, I0) = R9;        // after 2 missed beats fall back to audio clock
c_mp_unlocked:
      COMP(R0, R12);
      IF GE CALL c_tick;
c_mp_no_tick:
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
