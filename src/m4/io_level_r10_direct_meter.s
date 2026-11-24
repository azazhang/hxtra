@ Direct SHARC window peaks, protected SPI transport; no native or TAP fallback.
.syntax unified
.thumb
.equ CMD,0x1d
.equ REGISTER,0x28e165f1
.equ CHECK,0x28e19205
.equ REPLY,0x28e15b31
.equ RX_MAGIC,0xf00dface
.equ RX_END,0xecafd00f
.equ TAG,0x494f4d39
.equ UI_REDRAW,0x28db8509
.equ RECT_FILL,0x100017e9
.equ TTL,1150
.equ TICK,100
.equ HOLD,2
.equ BAR_BG,0x25282c
.equ GREEN,0x35c878
.equ AMBER,0xe9c84d
.equ ORANGE,0xf4a53a
.equ RED,0xd94242
@ Stats offsets: magic, lock, callbacks, accepted wire, bad checksum,
@ duplicate, last seq, accepted windows, gaps, last in/out, input calls,
@ DSP hot windows, M4 hot windows, age, packed live, pending,
@ packed display, packed holds, UI ticks, redraws, stale events,
@ rejected sequence, bad values, paint count, last painted, hot paints.
.thumb_func
r09_frame:
    push {r4-r11,lr}
    sub sp,#4
    mov r5,r1
    adr.w r4,r09_stats
    ldr r0,[r4,#4]
    adds r0,#1
    str r0,[r4,#4]
    dmb
    ldr r0,[r4,#8]
    adds r0,#1
    str r0,[r4,#8]
    ldr r0,[r5]
    ldr r1,=RX_MAGIC
    cmp r0,r1
    bne r09_age
    ldr.w r0,[r5,#1020]
    ldr r1,=RX_END
    cmp r0,r1
    bne r09_age
    ldr r0,[r5,#4]
    lsrs r0,#16
    cmp r0,#222
    bhi r09_age
    add.w r5,r5,#896
    ldr r0,[r5]
    ldr r1,=TAG
    cmp r0,r1
    beq r09_raw
    ror.w r0,r0,#16
    cmp r0,r1
    bne r09_age
    movs r11,#16
    b r09_read
r09_raw:
    movs r11,#0
r09_read:
    ldr r6,[r5,#4]
    ldr r7,[r5,#8]
    ldr r8,[r5,#12]
    ldr r9,[r5,#16]
    ldr r10,[r5,#20]
    ldr r0,[r5,#24]
    ror.w r6,r6,r11
    ror.w r7,r7,r11
    ror.w r8,r8,r11
    ror.w r9,r9,r11
    ror.w r10,r10,r11
    ror.w r0,r0,r11
    eor.w r1,r1,r6
    eors r1,r7
    eor.w r1,r1,r8
    eor.w r1,r1,r9
    eor.w r1,r1,r10
    mvns r1,r1
    cmp r0,r1
    bne r09_bad_crc
    ldr r0,=0x7f800000
    cmp r7,r0
    bhs r09_bad_values
    cmp r8,r0
    bhs r09_bad_values
    @ HW08: input callbacks are metadata, not a validity condition.
    @ 384 per window physically observed; keep exact instruction layout.
    nop.w
    nop
    cmp r6,#0
    beq r09_bad_values
    ldr r0,[r4,#12]
    adds r0,#1
    str r0,[r4,#12]
    ldr r0,[r4,#24]
    cmp r0,r6
    beq r09_duplicate
    cbz r0,r09_accept
    subs r1,r6,r0
    bmi r09_bad_seq
    subs r1,#1
    ldr r0,[r4,#32]
    adds r0,r1
    str r0,[r4,#32]
r09_accept:
    str r6,[r4,#24]
    ldr r0,[r4,#28]
    adds r0,#1
    str r0,[r4,#28]
    str r7,[r4,#36]
    str r8,[r4,#40]
    str r9,[r4,#44]
    str r10,[r4,#48]
    ldr r0,=0x3d0186e2
    cmp r8,r0
    blo r09_not_hot
    ldr r0,[r4,#52]
    adds r0,#1
    str r0,[r4,#52]
r09_not_hot:
    movs r0,#0
    str r0,[r4,#56]
    mov r0,r7
    bl r09_bin
    mov r6,r0
    mov r0,r8
    bl r09_bin
    orr.w r6,r6,r0,lsl #8
    str r6,[r4,#60]
    ldr r1,[r4,#64]
    uxtb r2,r1
    uxtb r3,r6
    cmp r2,r3
    it lo
    movlo r2,r3
    ubfx r1,r1,#8,#8
    ubfx r3,r6,#8,#8
    cmp r1,r3
    it lo
    movlo r1,r3
    orr.w r2,r2,r1,lsl #8
    str r2,[r4,#64]
    b r09_tick
r09_bad_crc:
    ldr r0,[r4,#16]
    adds r0,#1
    str r0,[r4,#16]
    b r09_age
r09_bad_values:
    ldr r0,[r4,#92]
    adds r0,#1
    str r0,[r4,#92]
    b r09_age
r09_bad_seq:
    ldr r0,[r4,#88]
    adds r0,#1
    str r0,[r4,#88]
    b r09_age
r09_duplicate:
    ldr r0,[r4,#20]
    adds r0,#1
    str r0,[r4,#20]
r09_age:
    ldr r0,[r4,#56]
    movw r1,#TTL
    cmp r0,r1
    bhs r09_tick
    adds r0,#1
    str r0,[r4,#56]
    cmp r0,r1
    bne r09_tick
    movs r0,#0
    str r0,[r4,#60]
    str r0,[r4,#64]
    str r0,[r4,#72]
    ldr r0,[r4,#84]
    adds r0,#1
    str r0,[r4,#84]
r09_tick:
    ldr r0,[r4,#76]
    adds r0,#1
    str r0,[r4,#76]
    cmp r0,#TICK
    blo r09_done
    movs r0,#0
    str r0,[r4,#76]
    bl r09_visual
    cbz r0,r09_done
    ldr r0,[r4,#80]
    adds r0,#1
    str r0,[r4,#80]
    movs r0,#0
    movs r1,#1
    ldr r3,=UI_REDRAW
    blx r3
r09_done:
    dmb
    ldr r0,[r4,#4]
    adds r0,#1
    str r0,[r4,#4]
    add sp,#4
    pop {r4-r11,pc}

@ IEEE-754 positive float bits sorted in numerical order; 16 dBFS marks.
.thumb_func
r09_bin:
    adr.w r1,r09_levels
    movs r2,#0
r09_bin_loop:
    ldr r3,[r1,r2,lsl #2]
    cmp r0,r3
    blo r09_bin_done
    adds r2,#1
    cmp r2,#16
    blo r09_bin_loop
r09_bin_done:
    mov r0,r2
    bx lr

@ Max-latch per display interval; two independent holds and bounded decay.
.thumb_func
r09_visual:
    push {r5-r11,lr}
    ldr r5,[r4,#68]
    ldr r6,[r4,#64]
    ldr r7,[r4,#60]
    ldr r8,[r4,#72]
    movs r9,#0
r09_visual_loop:
    lsr.w r10,r6,r9
    uxtb r10,r10
    lsr.w r11,r7,r9
    uxtb r11,r11
    cmp r10,r11
    it lo
    movlo r10,r11
    lsr.w r12,r5,r9
    uxtb r12,r12
    lsr.w r3,r8,r9
    uxtb r3,r3
    cmp r10,r12
    blo r09_decay
    mov r12,r10
    movs r3,#HOLD
    b r09_pack
r09_decay:
    cbz r3,r09_fall
    subs r3,#1
    b r09_pack
r09_fall:
    sub.w r0,r12,r10
    cmp r0,#2
    bls r09_floor
    sub.w r12,r12,#2
    b r09_pack
r09_floor:
    mov r12,r10
r09_pack:
    cmp r12,#16
    it hi
    movhi r12,#16
    movs r1,#255
    lsl.w r1,r1,r9
    bic.w r5,r5,r1
    bic.w r8,r8,r1
    lsl.w r0,r12,r9
    orr.w r5,r5,r0
    lsl.w r0,r3,r9
    orr.w r8,r8,r0
    adds r9,#8
    cmp r9,#16
    bne r09_visual_loop
    movs r0,#0
    str r0,[r4,#64]
    str r8,[r4,#72]
    ldr r1,[r4,#68]
    cmp r1,r5
    beq r09_visual_exit
    str r5,[r4,#68]
    movs r0,#1
r09_visual_exit:
    pop {r5-r11,pc}

.thumb_func
r09_draw:
    push {r4-r8,lr}
    mov r7,r0
    adr.w r4,r09_stats
    ldr r5,[r4,#96]
    adds r5,#1
    str r5,[r4,#96]
    ldr r6,[r4,#68]
    str r6,[r4,#100]
    ubfx r5,r6,#8,#8
    cmp r5,#6
    blo r09_draw_bg
    ldr r5,[r4,#104]
    adds r5,#1
    str r5,[r4,#104]
r09_draw_bg:
    ldr r4,=BAR_BG
    mov r0,r7
    movs r1,#24
    movs r2,#118
    movs r3,#132
    bl r09_fill
    mov r0,r7
    movs r1,#164
    movs r2,#118
    movs r3,#132
    bl r09_fill
    uxtb r5,r6
    movs r8,#26
    bl r09_row
    ubfx r5,r6,#8,#8
    movw r8,#166
    bl r09_row
    pop {r4-r8,pc}
.thumb_func
r09_row:
    push {r4-r10,lr}
    cmp r5,#16
    it hi
    movhi r5,#16
    cbz r5,r09_row_done
    movs r10,#0
r09_led_loop:
    ldr r4,=GREEN
    cmp r10,#10
    blo r09_led_paint
    ldr r4,=AMBER
    cmp r10,#13
    blo r09_led_paint
    ldr r4,=ORANGE
    cmp r10,#15
    blo r09_led_paint
    ldr r4,=RED
r09_led_paint:
    mov r0,r7
    add.w r1,r8,r10,lsl #3
    movs r2,#118
    movs r3,#7
    bl r09_fill
    adds r10,#1
    cmp r10,r5
    blo r09_led_loop
r09_row_done:
    pop {r4-r10,pc}
.thumb_func
r09_fill:
    push {r4,lr}
    sub sp,#16
    movs r12,#5
    str r12,[sp]
    str r4,[sp,#4]
    movs r12,#6
    str r12,[sp,#8]
    ldr r12,=RECT_FILL
    blx r12
    add sp,#16
    pop {r4,pc}

.align 2
r09_levels:
    .word 0x3a83126f
    .word 0x3b02c2f2
    .word 0x3b8273a6
    .word 0x3c02248a
    .word 0x3c81d59f
    .word 0x3d0186e2
    .word 0x3d813856
    .word 0x3db68738
    .word 0x3e00e9f9
    .word 0x3e361887
    .word 0x3e809bcc
    .word 0x3eb5aa1a
    .word 0x3f004dce
    .word 0x3f353bef
    .word 0x3f642905
    .word 0x3f800000
.thumb_func
r09_register:
    push {r4,lr}
    sub sp,#16
    adr.w r0,r09_command
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
r09_command:
    push {r4-r8,lr}
    sub sp,#8
    mov r7,r0
    ldrh r8,[r1,#12]
    adr.w r4,r09_stats
    adr.w r5,r09_reply
    movs r6,#4                 @ bounded retries; fail closed if busy
r09_reply_retry:
    ldr r2,[r4,#4]
    tst r2,#1
    bne r09_reply_again
    dmb
    movs r0,#0
r09_reply_copy:
    ldr r1,[r4,r0]
    str r1,[r5,r0]
    adds r0,#4
    cmp r0,#128
    blo r09_reply_copy
    dmb
    ldr r0,[r4,#4]
    cmp r0,r2
    beq r09_reply_send
r09_reply_again:
    subs r6,#1
    bne r09_reply_retry
    movs r0,#0
    str r0,[r5]                @ invalid magic: host rejects torn snapshot
r09_reply_send:
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
r09_stats:
    .word 0x41524f49            @ IOR9
    .space 124
    .byte 0
    .byte 0xc5,0x00,0x80
r09_reply:
    .space 128
.ltorg
