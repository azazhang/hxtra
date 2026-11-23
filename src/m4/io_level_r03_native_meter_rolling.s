@ IO-LEVEL-R03: two horizontal live bars from the verified native R01
@ 44-word / eight-record SHARC-to-M4 meter events.
@ Built on exact flashed R03C, preserving R01 read-only frame command 0x4f.
@ All DSP entries byte-identical. Native event group assignment:
@ first L/R pair -> LEFT trial bar; last L/R pair -> RIGHT trial bar.
@ Signal-path identity remains pending controlled physical amplitude testing.
@ R03 is an opt-in user-initiated RAM prototype, NOT updater-ready.
.syntax unified
.thumb
@ The original R01 0x4F raw frame command is unchanged. 0x13 only
@ returns rolling summary data captured by this module, without changing
@ device configuration, DSP, audio routing or metronome state.
.equ MTR_CMD,       0x13
.equ MTR_REGISTER,  0x28e165f1
.equ MTR_NO_PARAMS, 0x28e19205
.equ MTR_REPLY,     0x28e15b31
.equ MTR_REPLY_N,   67
.equ RX_MAGIC,      0xf00dface
.equ RX_END,        0xecafd00f
.equ RX44_HEADER,   0x00a81800      @ raw halfword-swapped DSP 0x180000a8
.equ RX44_FLAGS,    0x01100380      @ raw halfword-swapped DSP 0x03800110
.equ R02_TTL,       4600            @ approx 2s of RX frames without fresh 44-word update
.equ UI_REDRAW,     0x28db8509
.equ RECT_FILL,     0x100017e9
.equ BAR_Y,         118             @ y=113..117 using top-left anchor 6, below divider row119
.equ BAR_H,         5
.equ BAR_X_LEFT,    24              @ leaves existing GR Left/Right edge lanes alone
.equ BAR_X_RIGHT,   164
.equ BAR_W,         132
.equ BAR_STEP,      1
.equ BAR_BG,        0x25282c
.equ BAR_IN,        0x35c878
.equ BAR_OUT,       0x369ed8
.equ BAR_HOT,       0xf4a53a
.equ BAR_CLIP,      0xd94242

.thumb_func
io_meter_frame:
    push {r4-r8, lr}
    mov r4, r1
    adr.w r6, io_diag_live
    ldr r0, [r6, #4]
    adds r0, #1
    str r0, [r6, #4]              @ observed RX frames
    ldr.w r2, [r4, #4]             @ native payload words are in upper 16 RAW bits
    lsrs r2, #16
    cbz r2, io_native_empty
    ldr r0, [r6, #8]
    adds r0, #1
    str r0, [r6, #8]              @ native nonempty received
io_native_empty:
    cmp r2, #44
    bne io_no_update
    ldr r0, [r6, #12]
    adds r0, #1
    str r0, [r6, #12]             @ 44-word candidate
    ldr r2, [r4]
    ldr r3, =RX_MAGIC
    cmp r2, r3
    bne io_no_update
    ldr.w r2, [r4, #1020]
    ldr r3, =RX_END
    cmp r2, r3
    bne io_no_update
    ldr r2, [r4, #8]
    ldr r3, =RX44_HEADER
    cmp r2, r3
    bne io_no_update
    ldr r2, [r4, #12]
    ldr r3, =RX44_FLAGS
    cmp r2, r3
    bne io_no_update

    @ Validate native event record path 0, type 3, family 0x00020000.
    @ The eight-record pulse was seen unchanged in three real HW02 frames.
    @ Do NOT use arbitrary w10/w40 bytes when the buffer is stale or a
    @ different event layout is supplied.
    ldr.w r2, [r4, #24]             @ first event word0
    cmp r2, #0
    bne io_no_update
    ldr.w r2, [r4, #28]             @ first event type 3
    movw r3, #3
    lsls r3, #16
    cmp r2, r3
    bne io_no_update
    ldr.w r2, [r4, #32]             @ raw family 0x00020000 swapped
    cmp r2, #2
    bne io_no_update
    ldr.w r2, [r4, #36]             @ first ID 2
    ldr r3, =0x00020000
    cmp r2, r3
    bne io_no_update
    ldr.w r2, [r4, #56]             @ second ID 5
    ldr r3, =0x00050000
    cmp r2, r3
    bne io_no_update
    ldr.w r2, [r4, #156]            @ seventh ID 1
    ldr r3, =0x00010000
    cmp r2, r3
    bne io_no_update
    ldr.w r2, [r4, #176]            @ eighth ID 5
    ldr r3, =0x00050000
    cmp r2, r3
    bne io_no_update

    @ Snapshot ALL eight real native readings, including the unselected
    @ middle groups. This permits a direct Input vs Output identification
    @ by later USB diagnostic 0x13, without any DSP write or invented value.
    adr.w r6, io_diag_live
    ldr r2, [r4, #4]
    str r2, [r6, #28]             @ exact incoming native frame header
    add.w r7, r4, #40             @ raw w10, w15, ..., w45
    add.w r8, r6, #32             @ eight raw native float32s
    movs r0, #8
io_copy_levels:
    ldr.w r2, [r7]
    str.w r2, [r8], #4
    adds r7, #20
    subs r0, #1
    bne io_copy_levels
    dmb
    ldr r2, [r6, #16]
    adds r2, #1
    str r2, [r6, #16]             @ publish accepted packet count LAST

    @ LEFT trial pair is raw w10/w15. Compare UNSWAPPED IEEE floats
    @ as unsigned: among finite non-positive floats, smaller unsigned
    @ raw word means less negative dBFS (louder). No FPU in this thread.
    ldr.w r0, [r4, #40]
    ror.w r0, r0, #16
    ldr.w r2, [r4, #60]
    ror.w r2, r2, #16
    cmp r0, r2
    it hi
    movhi r0, r2
    bl io_level_to_bin
    mov r5, r0

    @ RIGHT trial pair is w40/w45, same hardware-verified packet layout.
    ldr.w r0, [r4, #160]
    ror.w r0, r0, #16
    ldr.w r2, [r4, #180]
    ror.w r2, r2, #16
    cmp r0, r2
    it hi
    movhi r0, r2
    bl io_level_to_bin
    orr.w r5, r5, r0, lsl #8
    orr r5, r5, #0x80000000      @ entire validated pair is atomic

    adr.w r6, io_bar_state
    movs r2, #0
    str r2, [r6, #4]             @ reset stale-frame counter
    ldr r2, [r6]
    cmp r5, r2
    beq io_meter_done
    str r5, [r6]
    adr.w r6, io_diag_live
    str r5, [r6, #24]             @ last rendered state
    ldr r2, [r6, #20]
    adds r2, #1
    str r2, [r6, #20]             @ number of distinct bar state updates
    b io_meter_repaint

io_no_update:
    adr.w r6, io_bar_state
    ldr r2, [r6, #4]
    movw r3, #R02_TTL
    cmp r2, r3
    bhi io_meter_done
    adds r2, #1
    str r2, [r6, #4]
    cmp r2, r3
    bls io_meter_done
    ldr r2, [r6]
    cmp r2, #0
    beq io_meter_done
    movs r2, #0
    str r2, [r6]
io_meter_repaint:
    movs r0, #0
    movs r1, #1
    ldr r3, =UI_REDRAW
    blx r3
io_meter_done:
    pop {r4-r8, pc}

@ Native IEEE754 float32 negative dB reading to 0..132 *pixels*.
@ Compute Q8(|dB|) by extracting exponent/significand; no M4 FPU
@ context touched in the USB/SPI RX callback. 1px ~0.68dB. Positive
@ finite dB values fill the bar; nonfinite values fail closed (empty).
.thumb_func
io_level_to_bin:
    ubfx r2, r0, #23, #8         @ IEEE exponent
    cmp r2, #255
    beq io_db_zero
    lsrs r3, r0, #31             @ sign
    cbz r3, io_db_full
    cmp r2, #127                 @ |dB| below 1: near full scale
    blo io_db_full
    cmp r2, #135                 @ |dB| >= 256: below floor
    bhs io_db_zero
    ubfx r3, r0, #0, #23
    orr r3, r3, #0x800000
    rsb.w r2, r2, #142            @ exponent to fixed Q8 shift
    lsr.w r3, r3, r2
    movw r2, #23040              @ 90 dB × 256
    cmp r3, r2
    bhs io_db_zero
    subs r2, r2, r3
    movs r3, #132
    mul r2, r3, r2
    movw r3, #23040
    udiv r0, r2, r3
    bx lr
io_db_full:
    movs r0, #132
    bx lr
io_db_zero:
    movs r0, #0
    bx lr

@ Hooked *after* the existing HXtra GR/Home/breathing paint function.
@ No widget structures are changed. These two compact stripes sit in
@ the Home screen's existing gap (rows 113..117) and x24..155/x164..295.
@ One 32bit packed state guarantees the two lengths belong to one update.
.thumb_func
io_meter_draw:
    push {r4-r8, lr}
    mov r7, r0                      @ framebuffer
    adr.w r6, io_bar_state
    ldr r6, [r6]                    @ packed bins (single atomic read)
    ldr r4, =BAR_BG
    mov r0, r7
    movs r1, #BAR_X_LEFT
    movs r2, #BAR_Y
    movs r3, #BAR_W
    bl io_fill_rect
    mov r0, r7
    movs r1, #BAR_X_RIGHT
    movs r2, #BAR_Y
    movs r3, #BAR_W
    bl io_fill_rect

    uxtb r5, r6                     @ left bar 0..10
    cbz r5, io_draw_right
    ldr r4, =BAR_IN
    cmp r5, #128
    blo io_l_normal
    ldr r4, =BAR_HOT
    cmp r5, #132
    it eq
    ldreq r4, =BAR_CLIP
io_l_normal:
    movs r3, #BAR_STEP
    mul r3, r5, r3
    mov r0, r7
    movs r1, #BAR_X_LEFT
    movs r2, #BAR_Y
    bl io_fill_rect
io_draw_right:
    ubfx r5, r6, #8, #8             @ right bar 0..10
    cbz r5, io_draw_done
    ldr r4, =BAR_OUT
    cmp r5, #128
    blo io_r_normal
    ldr r4, =BAR_HOT
    cmp r5, #132
    it eq
    ldreq r4, =BAR_CLIP
io_r_normal:
    movs r3, #BAR_STEP
    mul r3, r5, r3
    mov r0, r7
    movs r1, #BAR_X_RIGHT
    movs r2, #BAR_Y
    bl io_fill_rect
io_draw_done:
    pop {r4-r8, pc}

.thumb_func
io_fill_rect:                        @ r0 fb, r1 x, r2 y, r3 width, r4 colour
    push {r4, lr}
    sub sp, #16                     @ ABI: h at [sp], colour +4, anchor +8
    movs r12, #BAR_H
    str r12, [sp]
    str r4, [sp, #4]
    movs r12, #6                    @ left/top anchored: rows y-5..y-1
    str r12, [sp, #8]
    ldr r12, =RECT_FILL
    blx r12
    add sp, #16
    pop {r4, pc}

.align 2
io_bar_state:
    .word 0                          @ bit31 valid; 8..15 right pixels; 0..7 left pixels
    .word 0                          @ RX callbacks since last full 44-word event
@ Single additional registered editor request 0x13 (free on stock/R03C).
@ Signature + seven u32 summary counters/values + eight raw IEEE float32
@ samples in *as-captured halfword-swapped order*, 64 B in a BIN16 reply.
.thumb_func
io_diag_register:
    push {r4, lr}
    sub sp, #16
    adr.w r0, io_diag_command
    orr r0, r0, #1
    ldr r1, =MTR_NO_PARAMS
    movs r2, #0
    str r0, [sp, #4]
    str r1, [sp, #8]
    str r2, [sp, #12]
    movs r0, #MTR_CMD
    add r1, sp, #4
    ldr r3, =MTR_REGISTER
    blx r3
    add sp, #16
    pop {r4, pc}

.thumb_func
io_diag_command:
    push {r4-r8, lr}
    sub sp, #8
    mov r7, r0                        @ editor USB stream
    ldrh r8, [r1, #12]               @ read-only request sequence
    adr.w r4, io_diag_live
    adr.w r5, io_diag_reply_body
io_diag_retry:
    ldr r6, [r4, #16]                @ accepted-packet generation counter
    mov r1, r4
    mov r3, r5
    movs r2, #16                     @ 16 × u32 = 64 bytes
io_diag_copy:
    ldr.w r0, [r1], #4
    str.w r0, [r3], #4
    subs r2, #1
    bne io_diag_copy
    dmb
    ldr r0, [r4, #16]
    cmp r0, r6
    bne io_diag_retry                @ avoid torn RX packet payload
    movs r0, #MTR_REPLY_N
    str r0, [sp]
    mov r0, r7
    mov r1, r8
    movs r2, #0
    adr.w r3, io_diag_reply_body
    subs r3, #3                      @ exact BIN16 prefix before body
    ldr r12, =MTR_REPLY
    blx r12
    add sp, #8
    pop {r4-r8, pc}

@ Published rolling native metering stats. This is only M4 RAM, and
@ 0x13 is a read-only editor command. Live fields after 0x13 packet:
@   0: ASCII IOM3; 4: RX total; 8: nonempty; 12: 44-word candidates;
@   16: accepted 44-word meter packets; 20: bar changes; 24: bar state;
@   28: native header; 32..63: all eight 32-bit raw meter readings.
.align 2
io_diag_live:
    .word 0x334d4f49                 @ IOM3
    .space 60
    .byte 0                         @ 3-byte msgpack BIN16 before 4B body
io_diag_reply_prefix:
    .byte 0xc5, 0x00, 0x40          @ BIN16 with 64-byte payload
io_diag_reply_body:
    .word 0x334d4f49
    .space 60
.align 2
.ltorg
