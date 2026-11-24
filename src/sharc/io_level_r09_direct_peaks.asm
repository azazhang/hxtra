// Exact-R03C additive SHARC observer. Hooks only two existing instructions:
// 0xe4f6f in gate_sc's INPUT-meter-only continuation (before restore),
// 0xe503c in Main writer's continuation (before restore).
// Actual graph samples; no native event queue, no audio modification.
// 64 stereo Main blocks = 1024 samples/channel = 21.333 ms.
// Keep the window peak until next window; cumulative counters diagnose
// missed transfers even when host sampling is sparse. Publish through the
// two statically identified stock SPI TX DMA ring buffers (not RX c3cb6).
.equ IO_DM,0xe7440
.equ IO_PM,0xe4da0
.equ INPUT_RESTORE,0xe763d
.equ MAIN_I1,0xe7793
.equ MAIN_R0,0xe7795
.equ TX_A,0xc3eb6
.equ TX_B,0xc3fb6
.equ MAGIC1,0xFACEF00D
.equ MAGIC2,0xF00DFACE
.equ TRAIL1,0xD00FECAF
.equ TRAIL2,0xECAFD00F
.equ TAG,0x494F4D39
.equ HOT,0x3D0186E2 // approx 0.03162278 (-30 dBFS)
.section dm IO_DM
IN_ACC: .space 1
OUT_ACC: .space 1
BLOCKS: .space 1
IN_CALLS: .space 1
SEQ: .space 1
LAST_IN: .space 1
LAST_OUT: .space 1
LAST_IN_CALLS: .space 1
HOT_WINDOWS: .space 1
SAVE_R0: .space 1
SAVE_R1: .space 1
SAVE_R2: .space 1
SAVE_R3: .space 1
SAVE_R4: .space 1
SAVE_AX: .space 1
SAVE_AY: .space 1
.section pm IO_PM
INPUT_PEAK:
    DM(SAVE_AX) = ASTATX;
    DM(SAVE_AY) = ASTATY;
    DM(SAVE_R0) = R0;
    DM(SAVE_R1) = R1;
    I4 = I1;
    CALL peak16;
    R0 = DM(IN_ACC);
    F1 = MAX(F0,F1);
    DM(IN_ACC) = R1;
    R0 = DM(IN_CALLS);
    R0 = R0 + 1;
    DM(IN_CALLS) = R0;
    R0 = DM(SAVE_R0);
    R1 = DM(SAVE_R1);
    ASTATX = DM(SAVE_AX);
    ASTATY = DM(SAVE_AY);
    I4 = DM(INPUT_RESTORE);  // exact displaced instruction
    RTS;
MAIN_PEAK:
    DM(SAVE_AX) = ASTATX;
    DM(SAVE_AY) = ASTATY;
    DM(SAVE_R2) = R2;
    DM(SAVE_R3) = R3;
    DM(SAVE_R4) = R4;
    L4 = 0;
    I4 = DM(MAIN_I1);
    CALL peak16;
    R0 = DM(OUT_ACC);
    F1 = MAX(F0,F1);
    DM(OUT_ACC) = R1;
    R0 = DM(0,I0);
    R0 = PASS R0;
    IF EQ JUMP main_done;   // second channel completes stereo block
    R0 = DM(BLOCKS);
    R0 = R0 + 1;
    R1 = 64;
    COMP(R0,R1);
    IF LT JUMP retain_count;
    R0 = DM(IN_ACC);
    DM(LAST_IN) = R0;
    R1 = DM(OUT_ACC);
    DM(LAST_OUT) = R1;
    R0 = DM(IN_CALLS);
    DM(LAST_IN_CALLS) = R0;
    R0 = HOT;
    COMP(F1,F0);
    R0 = DM(HOT_WINDOWS);
    IF GE R0 = R0 + 1;
    DM(HOT_WINDOWS) = R0;
    R0 = DM(SEQ);
    R0 = R0 + 1;
    DM(SEQ) = R0;
    R0 = 0;
    DM(IN_ACC) = R0;
    DM(OUT_ACC) = R0;
    DM(IN_CALLS) = R0;
retain_count:
    DM(BLOCKS) = R0;
    R0 = DM(SEQ);
    R0 = PASS R0;
    IF EQ JUMP main_done;
    I4 = TX_A;
    CALL publish;
    I4 = TX_B;
    CALL publish;
main_done:
    R2 = DM(SAVE_R2);
    R3 = DM(SAVE_R3);
    R4 = DM(SAVE_R4);
    ASTATX = DM(SAVE_AX);
    ASTATY = DM(SAVE_AY);
    R0 = DM(MAIN_R0);       // exact displaced instruction
    RTS;
peak16:
    R1 = 0;
    LCNTR = 16, DO peak_last UNTIL LCE;
      F0 = DM(I4,1);
      F0 = ABS F0;
peak_last: F1 = MAX(F0,F1);
    RTS;
publish:
    R0 = DM(0,I4);
    R1 = MAGIC1;
    COMP(R0,R1);
    IF EQ JUMP normal;
    R1 = MAGIC2;
    COMP(R0,R1);
    IF NE RTS;
    R1 = TRAIL2;
    R0 = DM(1,I4);
    R0 = LSHIFT R0 BY -16;
    JUMP guard;
normal:
    R1 = TRAIL1;
    R0 = DM(1,I4);
    R0 = FEXT R0 BY 0:16;
guard:
    R2 = DM(255,I4);
    COMP(R2,R1);
    IF NE RTS;
    R1 = 222;
    COMPU(R0,R1);
    IF GT RTS;
    // Commit marker last. Same values stay for all frames in the window.
    // Clear marker while publishing; M4 additionally checks complement.
    R0 = 0;
    DM(224,I4) = R0;
    R3 = TAG;
    R0 = DM(SEQ);
    DM(225,I4) = R0;
    R3 = R3 XOR R0;
    R0 = DM(LAST_IN);
    DM(226,I4) = R0;
    R3 = R3 XOR R0;
    R0 = DM(LAST_OUT);
    DM(227,I4) = R0;
    R3 = R3 XOR R0;
    R0 = DM(LAST_IN_CALLS);
    DM(228,I4) = R0;
    R3 = R3 XOR R0;
    R0 = DM(HOT_WINDOWS);
    DM(229,I4) = R0;
    R3 = R3 XOR R0;
    R3 = NOT R3;
    DM(230,I4) = R3;
    R0 = TAG;
    DM(224,I4) = R0;
    RTS;
