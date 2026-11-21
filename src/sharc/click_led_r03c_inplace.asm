// M4 sender source: src/m4/metronome_led_r03c.s
// METRO-LEDSYNC-R03C-INPLACE: checked AND monotone 31bit LED events.
// Reject stale complete pairs, duplicate count and invalid complement; keep donor ABI.
// Original R03A donor kernel exactly retained outside this focused change.
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
// puts the next beat a new beat after the last (at once if that has passed), as a DAW's grid.

.equ C_SINCE,  20                       // samples since the last beat
.equ C_MET,    26
.equ C_LED_LAST, 28                // last validated 32bit event count
.equ LED_RING_WORD, 0xc3da6        // SHARC SPI RX word240; next is bitwise complement
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
    F8 = F8 * F9, R0 = DM(C_SINCE, I0);
    R12 = FIX F8, R1 = DM(C_MET, I0);
    R9 = MIN_BEAT;
    R12 = MAX(R12, R9), R13 = DM(C_BEAT, I0);
    R9 = MAX_BEAT;
    R12 = MIN(R12, R9), F2 = DM(C_Y2, I0);

    F8 = DM(6, I0);                     // Level: 0.5 x 2^(dB / 20 log2 10), 2^f by a cubic
    F9 = 0.16609640474;
    F8 = F8 * F9, F3 = DM(C_COEF, I0);
    F9 = 16.0;                          // (+16 keeps it positive for TRUNC: dB >= -96)
    F8 = F8 + F9, F4 = DM(C_ENV, I0);
    R10 = TRUNC F8, R7 = DM(8, I0);
    F11 = FLOAT R10, R14 = DM(7, I0);
    F8 = F8 - F11;
    F6 = 5.963386535644532e-07;
    F6 = F6 * F8;
    F9 = 1.7254531860351562e-06;
    F6 = F6 + F9;
    F6 = F6 * F8;
    F9 = 5.303791809082031e-06;
    F6 = F6 + F9;
    F6 = F6 * F8;
    F9 = 0.00000762939453125;
    F6 = F6 + F9;
    // Gain polynomial factored by exact power-of-two 2^-17; SCALB uses R10.
    F6 = SCALB F6 BY R10;

    F7 = FLOAT R7;                   // model boolean: exactly 0/1

    // R14 already loaded from model Accent (valid integer 1..12).

    // R0 and R1 loaded in parallel with period computation.
    R1 = PASS R1;
    IF EQ R0 = PASS R12;
    R1 = 1;
    DM(C_MET, I0) = R1;
    // R13, F4, F2, F3 already loaded during Level/period math.
    F5 = 0.99653379;                    // the envelope's step: a 6 ms time constant

    // Two-word full 32bit complement, M4-stamped into unused SPI slots
    // 240/241 after stock TX completed. One invalid/torn pair cannot click.
    // No R1..R5 scratch use: oscillator float state has already been hoisted.
    R8 = DM(LED_RING_WORD);
    R9 = NOT R8, F1 = DM(C_Y1, I0);
    R10 = DM(LED_RING_WORD + 1);
    COMP(R9, R10);
    IF NE JUMP c_led_invalid;
    R9 = DM(C_LED_LAST, I0);
    R11 = R8 XOR R9;                 // retain epoch change for downbeat
    R10 = R8 - R9;
    R10 = LSHIFT R10 BY 1;           // discard bit31 epoch; signed count delta*2
    IF LE R0 = R0 - R0;             // duplicate or replayed old frame: silent
    IF GT R0 = PASS R12, DM(C_LED_LAST, I0) = R8; // fresh beat and commit
    IF LE R11 = R11 - R11;         // stale epoch MUST NOT reset accent
    BTST R11 BY 31;
    IF NOT SZ R13 = R13 - R13;       // fresh epoch: downbeat only
    JUMP c_led_next;
c_led_invalid:
    R8 = PASS R8;
    IF NE R0 = R0 - R0;              // malformed nonzero pair: silence
    // Zero is an explicit off-TAP/no-LED transport mode: donor local clock.
c_led_next:

    LCNTR = 16, DO c_last UNTIL LCE;
      COMP(R0, R12);
      IF GE CALL c_tick;
      R0 = R0 + 1, F10 = DM(I4, 1);
      F8 = F3 * F1;                     // the oscillator: y = 2 cos w y1 - y2
      F8 = F8 - F2;
      F2 = PASS F1;
      F1 = PASS F8;
      F9 = F8 * F4;
      F4 = F4 * F5;
      F9 = F9 * F6;
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

    NOP;  // unreachable record-size padding after final RTS
