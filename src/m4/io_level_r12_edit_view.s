@ Edit view overlay, preserves R11 Play draw and exact SHARC path.
.syntax unified
.thumb
.equ STATS,0x28e626f0
.equ RECT_FILL,0x100017e9
.equ BAR_BG,0x25282c
.equ GREEN,0x35c878
.equ AMBER,0xe9c84d
.equ ORANGE,0xf4a53a
.equ RED,0xd94242
.equ EDIT_A,0x28128270
.equ EDIT_B,0x281282f8
.equ LIST_A,0x281f35b8
.equ LIST_B,0x281f3d2c
.thumb_func
edit_params:
    ldr r2,=EDIT_A
    cmp r1,r2
    beq edit_guard
    bx lr
.thumb_func
edit_top:
    ldr r2,=EDIT_B
    cmp r1,r2
    beq edit_guard
    bx lr
.thumb_func
edit_guard:
    push {r4,lr}
    mov r4,r0
    ldr r0,=LIST_A
    bl edit_active
    ldr r1,=EDIT_A
    cmp r0,r1
    bne edit_skip
    ldr r0,=LIST_B
    bl edit_active
    ldr r1,=EDIT_B
    cmp r0,r1
    bne edit_skip
    mov r0,r4
    bl edit_draw
edit_skip:
    pop {r4,pc}

@ Mirror the stock first-active-node rule. Bound traversal to avoid
@ a malformed or changing list causing an unbounded paint callback.
.thumb_func
edit_active:
    ldr r0,[r0]
    movs r2,#32
edit_node:
    cbz r0,edit_none
    ldr r1,[r0]
    lsls r1,r1,#31
    bmi edit_found
    ldr r0,[r0,#0x14]
    subs r2,#1
    bne edit_node
edit_none:
    movs r0,#0
    bx lr
edit_found:
    ldr r1,[r0,#4]
    cmp r1,#0
    ite ne
    ldrne r0,[r0,#0xc]
    moveq r0,#0
    bx lr

.thumb_func
edit_draw:
    push {r4-r8,lr}
    mov r7,r0
    ldr r4,=STATS
    ldr r5,[r4,#108]
    adds r5,#1
    str r5,[r4,#108]
    ldr r5,[r4,#96]
    adds r5,#1
    str r5,[r4,#96]
    ldr r6,[r4,#68]
    str r6,[r4,#100]
    ubfx r5,r6,#8,#8
    cmp r5,#10            @ -30 dBFS on the uniform 5 dB scale
    blo edit_draw_bg
    ldr r5,[r4,#104]
    adds r5,#1
    str r5,[r4,#104]
edit_draw_bg:
    ldr r4,=BAR_BG
    mov r0,r7
    movs r1,#24
    movs r2,#133
    movs r3,#132
    bl edit_fill
    mov r0,r7
    movs r1,#164
    movs r2,#133
    movs r3,#132
    bl edit_fill
    uxtb r5,r6
    movs r8,#26
    bl edit_row
    ubfx r5,r6,#8,#8
    movw r8,#166
    bl edit_row
    pop {r4-r8,pc}
.thumb_func
edit_row:
    push {r4-r10,lr}
    cmp r5,#16
    it hi
    movhi r5,#16
    cbz r5,edit_row_done
    movs r10,#0
edit_led_loop:
    ldr r4,=GREEN
    cmp r10,#10
    blo edit_led_paint
    ldr r4,=AMBER
    cmp r10,#13
    blo edit_led_paint
    ldr r4,=ORANGE
    cmp r10,#15
    blo edit_led_paint
    ldr r4,=RED
edit_led_paint:
    mov r0,r7
    add.w r1,r8,r10,lsl #3
    movs r2,#133
    movs r3,#7
    bl edit_fill
    adds r10,#1
    cmp r10,r5
    blo edit_led_loop
edit_row_done:
    pop {r4-r10,pc}
.thumb_func
edit_fill:
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

