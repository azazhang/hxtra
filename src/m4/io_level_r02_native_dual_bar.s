@ IO-LEVEL-R02: two horizontal live bars from the verified native R01
@ 44-word / eight-record SHARC-to-M4 meter events.
@ Built on exact flashed R03C, preserving R01 read-only frame command 0x4f.
@ All DSP entries byte-identical. Native event group assignment:
@ first L/R pair -> LEFT trial bar; last L/R pair -> RIGHT trial bar.
@ Signal-path identity remains pending controlled physical amplitude testing.
@ R02 is an opt-in user-initiated RAM prototype, NOT updater-ready.
.syntax unified
.thumb
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
.equ BAR_STEP,      13
.equ BAR_BG,        0x25282c
.equ BAR_IN,        0x35c878
.equ BAR_OUT,       0x369ed8
.equ BAR_HOT,       0xf4a53a
.equ BAR_CLIP,      0xd94242

.thumb_func
io_meter_frame:
    push {r4-r8, lr}
    mov r4, r1
    ldr.w r2, [r4, #4]             @ native payload words are in upper 16 RAW bits
    lsrs r2, #16
    cmp r2, #44
    bne io_no_update
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

@ r0 = IEEE float32 negative dBFS, in canonical halfword order.
@ Return r0 = 0..10 bins at -90, -72, -60, -48, -36, -24, -18,
@ -12, -6 and -3 dBFS; bin10 means above -3 dBFS.
@ Common comparator accepts positive values as over-scale bin10.
@ NaN/Inf are not expected from native 0x2390, but reject if seen.
.thumb_func
io_level_to_bin:
    ubfx r2, r0, #23, #8
    cmp r2, #255
    beq io_bad_float
    ldr r2, =0xc2b40000            @ -90
    cmp r0, r2
    bhs io_bin0
    ldr r2, =0xc2900000            @ -72
    cmp r0, r2
    bhs io_bin1
    ldr r2, =0xc2700000            @ -60
    cmp r0, r2
    bhs io_bin2
    ldr r2, =0xc2400000            @ -48
    cmp r0, r2
    bhs io_bin3
    ldr r2, =0xc2100000            @ -36
    cmp r0, r2
    bhs io_bin4
    ldr r2, =0xc1c00000            @ -24
    cmp r0, r2
    bhs io_bin5
    ldr r2, =0xc1900000            @ -18
    cmp r0, r2
    bhs io_bin6
    ldr r2, =0xc1400000            @ -12
    cmp r0, r2
    bhs io_bin7
    ldr r2, =0xc0c00000            @ -6
    cmp r0, r2
    bhs io_bin8
    ldr r2, =0xc0400000            @ -3
    cmp r0, r2
    bhs io_bin9
    movs r0, #10
    bx lr
io_bin0:
io_bad_float:
    movs r0, #0
    bx lr
io_bin1:
    movs r0, #1
    bx lr
io_bin2:
    movs r0, #2
    bx lr
io_bin3:
    movs r0, #3
    bx lr
io_bin4:
    movs r0, #4
    bx lr
io_bin5:
    movs r0, #5
    bx lr
io_bin6:
    movs r0, #6
    bx lr
io_bin7:
    movs r0, #7
    bx lr
io_bin8:
    movs r0, #8
    bx lr
io_bin9:
    movs r0, #9
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
    cmp r5, #10
    it eq
    ldreq r4, =BAR_CLIP
    cmp r5, #9
    it eq
    ldreq r4, =BAR_HOT
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
    cmp r5, #10
    it eq
    ldreq r4, =BAR_CLIP
    cmp r5, #9
    it eq
    ldreq r4, =BAR_HOT
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
    .word 0                          @ 31=valid; 8..15 right bin; 0..7 left bin
    .word 0                          @ RX callbacks since last full 44-word event
.ltorg
