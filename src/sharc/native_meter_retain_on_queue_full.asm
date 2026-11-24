// R07: stock meter 0x2390 at PM 0x8da6a; replace ONLY seven words.
// At 0x8da7c the period counter is already stored. The stock duplicate
// store at 0x8da7e is redundant; use its slot for the delayed CALL.
// Stock 0x8cbb8 returns 0 if enqueued, -1 if the shared queue is full.
// The peak must survive a rejected event, so it is included in the next
// normal publication window. Do not increase reporting rate, change the
// audio signal or invent a measurement. Preserve R0=0 return and flags.
.section pm 0x8da7e
    CALL 0x8cbb8 (DB);
    R1 = 1;
    R3 = R3 XOR R3, R0 = DM(1,I0);
    R0 = R0 OR R0;                     // test success without clobbering AN
    RTS (DB, LR);
    IF EQ PM(0,I8) = R0;               // only clear on successful enqueue
    R0 = R0 XOR R0;                    // same return R0/ALU flags as original
