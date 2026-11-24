@ R08: read-only observer of the actual I2S->USB audio ring in shared SRAM.
@ No SHARC/M0 code, audio data, descriptor, routing or display modifications.
@ Exact R03C M0 disassembly: 0x20003390 receive cursor +40/+46, 64-bit
@ word count +50/+54; descriptor array 0x20007a80 (8*32), buffers
@ 0x2000b3f0+224*i. Descriptor +14 completed length, +18 target length.
@ Producer increments count before storing the word. Only read completed
@ descriptors with a subsequent word begun; verify phase and coverage;
@ reject if producer overtakes the oldest descriptor while reading.
.syntax unified
.thumb
.equ CTX,0x20006338
.equ DESCS,0x20007a80
.equ BUF,0x2000b3f0
.equ CMD,0x1d
.equ REGISTER,0x28e165f1
.equ CHECK,0x28e19205
.equ REPLY,0x28e15b31
.equ HOT40,83887  @ signed 24-bit PCM amplitude, approximately -40 dBFS
.equ HOT30,265271
.equ HOT50,26527
@ stats: 0 magic, 4 seqlock, 8 calls, 12 unstable cursor, 16 seeds/resync,
@ 20 valid commits, 24 accepted sample frames, 28 rejected complete batches,
@ 32 skipped words (exact boundary delta on resync), 36 last producer count,
@ 40 last completed boundary, 44 next descriptor idx, 48 seeded,
@ 52 last input max, 56 last output max, 60 max input, 64 max output,
@ 68 input >-40, 72 output >-40, 76 output >-30, 80 output >-50,
@ 84 descriptor/header failures, 88 marker failures, 92 overtake failures,
@ 96 last observed idx, 100 last observed offset, 104 current descriptor len,
@ 108 last boundary advance, 112 cursor resets, 116 last completed length,
@ 120 nonactive count, 124 max batch frames.
.thumb_func
pcm_ring_frame:
    push {r4-r11, lr}
    sub sp,#52                  @ aligned total 88 bytes
    adr.w r4, pcm_stats
    ldr r0,[r4,#4]
    adds r0,#1
    str r0,[r4,#4]
    dmb
    ldr r0,[r4,#8]
    adds r0,#1
    str r0,[r4,#8]
    ldr r5,=CTX
    ldr r0,[r5,#0x30]
    ldr r1,=DESCS
    cmp r0,r1
    bne pcm_inactive
    ldr r0,[r5,#0x1c]
    ldr r1,=BUF
    cmp r0,r1
    bne pcm_inactive
    @ Snapshot cursor. Validate the same producer word count, index and
    @ offset twice. On an in-flight update skip; never spin in RX context.
    ldr r6,[r5,#0x50]
    ldrb r7,[r5,#0x40]
    ldrh r8,[r5,#0x46]
    dmb
    ldr r0,[r5,#0x50]
    cmp r0,r6
    bne pcm_unstable
    ldrb r0,[r5,#0x40]
    cmp r0,r7
    bne pcm_unstable
    ldrh r0,[r5,#0x46]
    cmp r0,r8
    bne pcm_unstable
    str r6,[r4,#36]
    str r7,[r4,#96]
    str r8,[r4,#100]
    cmp r7,#7
    bhi pcm_inactive
    cmp r8,#4
    blo pcm_unstable
    cmp r8,#224
    bhi pcm_unstable
    tst r8,#3
    bne pcm_unstable
    ldr r0,=DESCS
    add.w r0,r0,r7,lsl #5
    ldr r1,[r0,#0x18]
    str r1,[r4,#104]
    cmp r1,#192
    beq pcm_len_ok
    cmp r1,#224
    bne pcm_inactive
pcm_len_ok:
    cmp r8,r1
    bhi pcm_unstable
    lsr.w r0,r8,#2
    cmp r6,r0
    blo pcm_unstable
    sub.w r9,r6,r0              @ completed-boundary word counter
    ldr r0,[r4,#48]
    cmp r0,#0
    beq.w pcm_seed
    ldr r0,[r4,#40]
    subs.w r10,r9,r0            @ new completed words (u32)
    str r10,[r4,#108]
    cmp r10,#0
    beq pcm_done
    ldr r11,[r4,#44]
    sub.w r0,r7,r11
    ands r0,r0,#7              @ count of new complete descriptors
    str r0,[sp,#0]
    cmp r10,#336               @ 6 * 56 words; bounded work and ring safety
    bhi pcm_resync
    cmp r0,#1
    blo pcm_unstable            @ transition / count inconsistent, retry later
    cmp r0,#6
    bhi pcm_resync
    @ Local batch accumulators, commit only when all validation succeeds.
    movs r0,#0
    str r0,[sp,#4]              @ validated words
    str r0,[sp,#8]              @ input max
    str r0,[sp,#12]             @ output max
    str r0,[sp,#16]             @ input hot -40
    str r0,[sp,#20]             @ output hot -40
    str r0,[sp,#24]             @ output hot -30
    str r0,[sp,#28]             @ output hot -50
    str r0,[sp,#32]             @ last descriptor length
    ldr r0,[sp,#0]
    str r0,[sp,#36]             @ remaining descriptors
pcm_desc:
    ldr r0,=DESCS
    add.w r0,r0,r11,lsl #5
    ldr r1,[r0,#0x10]
    movs r2,#224
    mul r2,r2,r11
    ldr r3,=BUF
    add r2,r3
    cmp r1,r2                   @ never dereference an arbitrary descriptor ptr
    bne pcm_bad_desc
    ldr r2,[r0,#0x14]          @ producer's completed length, not USB target
    cmp r2,#192
    beq pcm_desc_len
    cmp r2,#224
    bne pcm_bad_desc
pcm_desc_len:
    str r2,[sp,#32]
    ldr r0,[sp,#4]
    add.w r0,r0,r2,lsr #2
    str r0,[sp,#4]
    adds r2,r1
    str r2,[sp,#40]             @ end address, bounded to fixed SRAM ring
pcm_sample:
    @ bit 0 of first word is frame sync; other 7 slots must have bit0=0.
    ldr r0,[r1,#0]
    tst r0,#1
    beq pcm_bad_marker
    ldr r2,[r1,#4]
    tst r2,#1
    bne pcm_bad_marker
    ldr r3,[r1,#8]
    ldr r12,[r1,#12]
    orrs r3,r12
    ldr r12,[r1,#16]
    orrs r3,r12
    ldr r12,[r1,#20]
    orrs r3,r12
    ldr r12,[r1,#24]
    orrs r3,r12
    ldr r12,[r1,#28]
    orrs r3,r12
    tst r3,#1
    bne pcm_bad_marker
    @ PCM24 in upper 24 bits, ignore synchronization bit / padding.
    asrs r0,r0,#8
    it mi
    rsbmi r0,r0,#0
    asrs r2,r2,#8
    it mi
    rsbmi r2,r2,#0
    cmp r0,r2
    it lo
    movlo r0,r2                 @ Main USB 1/2 stereo max
    ldr r2,[sp,#12]
    cmp r0,r2
    it hi
    strhi r0,[sp,#12]
    ldr r3,=HOT50
    cmp r0,r3
    blo pcm_out40_done
    ldr r2,[sp,#28]
    adds r2,#1
    str r2,[sp,#28]
    ldr r3,=HOT40
    cmp r0,r3
    blo pcm_out40_done
    ldr r2,[sp,#20]
    adds r2,#1
    str r2,[sp,#20]
    ldr r3,=HOT30
    cmp r0,r3
    blo pcm_out40_done
    ldr r2,[sp,#24]
    adds r2,#1
    str r2,[sp,#24]
pcm_out40_done:
    ldr r0,[r1,#16]
    ldr r2,[r1,#20]
    asrs r0,r0,#8
    it mi
    rsbmi r0,r0,#0
    asrs r2,r2,#8
    it mi
    rsbmi r2,r2,#0
    cmp r0,r2
    it lo
    movlo r0,r2                 @ dry USB 5/6 stereo max
    ldr r2,[sp,#8]
    cmp r0,r2
    it hi
    strhi r0,[sp,#8]
    ldr r3,=HOT40
    cmp r0,r3
    blo pcm_in40_done
    ldr r2,[sp,#16]
    adds r2,#1
    str r2,[sp,#16]
pcm_in40_done:
    adds r1,#32
    ldr r2,[sp,#40]
    cmp r1,r2
    blo pcm_sample
    ldr r0,[sp,#36]
    subs r0,#1
    str r0,[sp,#36]
    add.w r11,r11,#1
    and r11,r11,#7
    cmp r0,#0
    bne pcm_desc
    ldr r0,[sp,#4]
    cmp r0,r10                  @ proves complete coverage of this boundary delta
    bne pcm_bad_desc
    cmp r11,r7
    bne pcm_bad_desc
    dmb
    @ If producer wrapped to oldest descriptor during scan, discard batch.
    ldr r0,[r5,#0x50]
    subs r0,r0,r6
    cmp r0,#56
    bhi pcm_overtake
    ldrb r0,[r5,#0x40]
    subs r0,r0,r7
    and r0,r0,#7
    ldr r1,[sp,#0]
    rsb r1,r1,#8
    cmp r0,r1
    bhs pcm_overtake
    @ All reads accounted for and not overwritten; publish atomically.
    ldr r0,[r4,#20]
    adds r0,#1
    str r0,[r4,#20]
    lsr.w r0,r10,#3            @ 8 audio words per sample frame
    ldr r1,[r4,#24]
    adds r1,r0
    str r1,[r4,#24]
    ldr r1,[r4,#124]
    cmp r0,r1
    it hi
    strhi r0,[r4,#124]
    ldr r0,[sp,#8]
    str r0,[r4,#52]
    ldr r1,[r4,#60]
    cmp r0,r1
    it hi
    strhi r0,[r4,#60]
    ldr r0,[sp,#12]
    str r0,[r4,#56]
    ldr r1,[r4,#64]
    cmp r0,r1
    it hi
    strhi r0,[r4,#64]
    ldr r0,[sp,#16]
    ldr r1,[r4,#68]
    adds r0,r1
    str r0,[r4,#68]
    ldr r0,[sp,#20]
    ldr r1,[r4,#72]
    adds r0,r1
    str r0,[r4,#72]
    ldr r0,[sp,#24]
    ldr r1,[r4,#76]
    adds r0,r1
    str r0,[r4,#76]
    ldr r0,[sp,#28]
    ldr r1,[r4,#80]
    adds r0,r1
    str r0,[r4,#80]
    ldr r0,[sp,#32]
    str r0,[r4,#116]
    b pcm_advance
pcm_bad_desc:
    ldr r0,[r4,#84]
    adds r0,#1
    str r0,[r4,#84]
    b pcm_rejected
pcm_bad_marker:
    ldr r0,[r4,#88]
    adds r0,#1
    str r0,[r4,#88]
    b pcm_rejected
pcm_overtake:
    ldr r0,[r4,#92]
    adds r0,#1
    str r0,[r4,#92]
pcm_rejected:
    ldr r0,[r4,#28]
    adds r0,#1
    str r0,[r4,#28]
    @ Leave cursor for retry. If ring runs past, explicit resync below.
    b pcm_done
pcm_resync:
    @ A backwards count (USB stop/reset) is not a huge dropped-word count.
    tst r10,#0x80000000
    bne pcm_reset
    ldr r0,[r4,#32]
    adds r0,r10
    str r0,[r4,#32]
    b pcm_seed
pcm_reset:
    ldr r0,[r4,#112]
    adds r0,#1
    str r0,[r4,#112]
pcm_seed:
    ldr r0,[r4,#16]
    adds r0,#1
    str r0,[r4,#16]
    movs r0,#1
    str r0,[r4,#48]
pcm_advance:
    str r9,[r4,#40]
    str r7,[r4,#44]
    b pcm_done
pcm_inactive:
    ldr r0,[r4,#120]
    adds r0,#1
    str r0,[r4,#120]
    movs r0,#0
    str r0,[r4,#48]
    b pcm_done
pcm_unstable:
    ldr r0,[r4,#12]
    adds r0,#1
    str r0,[r4,#12]
pcm_done:
    dmb
    ldr r0,[r4,#4]
    adds r0,#1
    str r0,[r4,#4]
    add sp,#52
    pop {r4-r11,pc}

.thumb_func
pcm_register:
    push {r4,lr}
    sub sp,#16
    adr.w r0,pcm_command
    orr r0,r0,#1
    ldr r1,=CHECK
    movs r2,#0
    str r0,[sp,#4]
    str r1,[sp,#8]
    str r2,[sp,#12]
    movs r0,#CMD
    add r1,sp,#4
    ldr r3,=REGISTER
    blx r3
    add sp,#16
    pop {r4,pc}
.thumb_func
pcm_command:
    push {r4-r8,lr}
    sub sp,#8
    mov r7,r0
    ldrh r8,[r1,#12]
    adr.w r4,pcm_stats
    adr.w r5,pcm_reply
    movs r6,#4                 @ bounded retries; fail closed if busy
pcm_reply_retry:
    ldr r2,[r4,#4]
    tst r2,#1
    bne pcm_reply_again
    dmb
    movs r0,#0
pcm_reply_copy:
    ldr r1,[r4,r0]
    str r1,[r5,r0]
    adds r0,#4
    cmp r0,#128
    blo pcm_reply_copy
    dmb
    ldr r0,[r4,#4]
    cmp r0,r2
    beq pcm_reply_send
pcm_reply_again:
    subs r6,#1
    bne pcm_reply_retry
    movs r0,#0
    str r0,[r5]                @ invalid magic: host rejects torn snapshot
pcm_reply_send:
    movs r0,#131
    str r0,[sp]
    mov r0,r7
    mov r1,r8
    movs r2,#0
    subs r3,r5,#3
    ldr r12,=REPLY
    blx r12
    add sp,#8
    pop {r4-r8,pc}
.align 2
pcm_stats:
    .word 0x38524f49            @ IOR8
    .space 124
    .byte 0
    .byte 0xc5,0x00,0x80
pcm_reply:
    .space 128
.ltorg
