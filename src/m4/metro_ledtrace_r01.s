@ METRO-LEDSYNC-M4LEDTRACE-R01: exact HXtra v1.2.1 M4-only event-timing diagnostic.
@ TWO original-entry hook sites: post-filter FS3 LED send + editor registration.
@ SHARC bootstream, SPI TX/RX callbacks, bypass handling, and all donor
@ globals/features are untouched. No configuration writes.
@ Record actual final LED colour transitions and timestamp each with the same
@ microsecond clock the original tap tempo/beat tasks use.
.syntax unified
.thumb
.include "usb.inc"
.equ REGISTER,     0x28e165f1
.equ NO_PARAMS,    0x28e19205
.equ REPLY_SEND,   0x28e15b31
.equ LED_CONT,     0x28d98f7d
.equ FS3_FUNCTION, 0x28128a78
.equ TIME_US,      0x28da6459
.equ TRACE_SLOTS,  16
.equ TRACE_BYTES,  144
.equ PAYLOAD_BYTES,148
.equ REPLY_BYTES,  150
.equ BUILD_TAG,    0x31474c4d  @ little-endian "MLG1"
.thumb_func
.global mt_led_entry
mt_led_entry:
    push {r0-r4, lr}
    @ HXtra's original LED continuation can arrive with SP mod 8 = 4.
    @ Align only for the nested timer call; restore the exact incoming SP.
    mov r4, sp
    and.w r4, r4, #7
    cbz r4, mt_led_aligned
    sub sp, #4
mt_led_aligned:
    bl mt_capture
    cmp r4, #0
    beq mt_led_restored
    add sp, #4
mt_led_restored:
    pop {r0-r4, lr}
    sub sp, #20                   @ displaced exact donor instructions
    ldrb r2, [r3, #0]
    ldr r12, =LED_CONT
    bx r12

@ M4 LED callback receives r0=ring index, r1=post-HX_BPM RGB.
@ Single-core odd/even generation protocol protects the USB reader from
@ partially written ring slots; a non-TAP FS3 invalidates remembered state.
.thumb_func
mt_capture:
    push {r4-r8, lr}             @ 24 bytes, 8-byte aligned for TIME_US
    cmp r0, #2
    bne mt_cap_done
    ldr r4, =FS3_FUNCTION
    ldrb r4, [r4]
    cmp r4, #1
    bne mt_cap_not_tap
    movs r5, #0
    cmp r1, #0
    beq mt_cap_have_state
    movs r5, #1
mt_cap_have_state:
    adr.w r4, mt_state
    ldr r6, [r4, #12]            @ previous lit (0/1)
    cmp r5, r6
    beq mt_cap_done              @ only transitions, not redundant RGB sends
    ldr r7, =TIME_US
    blx r7                       @ hardware microsecond time, same as stock TAP
    adr.w r4, mt_state
    ldr r6, [r4, #4]             @ generation, always even outside writes
    adds r6, #1
    str r6, [r4, #4]             @ writer active: odd
    dmb
    ldr r8, [r4, #8]             @ committed edge sequence
    adds r8, #1
    and.w r7, r8, #15
    lsls r7, r7, #3              @ two 32-bit words per ring slot
    adds r7, r4
    adds r7, #16
    str r0, [r7]                 @ timestamp first
    lsls r1, r8, #1
    orrs r1, r5                  @ sequence << 1 | visible state
    str r1, [r7, #4]
    str r8, [r4, #8]
    str r5, [r4, #12]
    dmb
    adds r6, #1
    str r6, [r4, #4]             @ writer complete: even
    b mt_cap_done
mt_cap_not_tap:
    adr.w r4, mt_state
    movs r5, #0
    str r5, [r4, #12]            @ next TAP mode illumination starts a new edge
mt_cap_done:
    pop {r4-r8, pc}

.thumb_func
mt_register:
    push {r4, lr}
    sub sp, #16
    adr.w r0, mt_command
    orr r0, r0, #1
    ldr r1, =NO_PARAMS
    movs r2, #0
    str r0, [sp, #4]
    str r1, [sp, #8]
    str r2, [sp, #12]
    movs r0, #CMD
    add r1, sp, #4
    ldr r3, =REGISTER
    blx r3
    add sp, #16
    pop {r4, pc}

@ MSGPACK BIN8(148). The final u32 is generation read after copying.
@ Accept only when initial/final generations are equal and even.
@ Payload: tag, gen_before, edge_seq, current_lit, 16x(timestamp_us,seq2|lit), gen_after.
.thumb_func
mt_command:
    push {r4-r8, lr}
    sub sp, #8
    mov r7, r0
    ldrh r8, [r1, #0xc]
    adr.w r4, mt_state
    adr.w r5, mt_reply
    add r5, #2
    ldr r0, [r4, #4]             @ aligned atomic generation read BEFORE copy
    str r0, [sp, #4]
    movs r6, #0
mt_copy:
    ldrb r0, [r4, r6]
    strb r0, [r5, r6]
    adds r6, #1
    cmp r6, #TRACE_BYTES
    blo mt_copy
    ldr r0, [sp, #4]             @ overwrite byte-copied field with atomic before value
    str r0, [r5, #4]
    dmb
    ldr r0, [r4, #4]
    str r0, [r5, #TRACE_BYTES]
    movs r0, #REPLY_BYTES
    str r0, [sp]
    mov r0, r7
    mov r1, r8
    movs r2, #0
    adr.w r3, mt_reply
    ldr r12, =REPLY_SEND
    blx r12
    add sp, #8
    pop {r4-r8, pc}

.align 2
mt_state:
    .word BUILD_TAG                 @ exact firmware identity
    .word 0                         @ writer generation
    .word 0                         @ LED command transition sequence
    .word 0                         @ previous lit state
    .space 128                      @ 16*(u32 timestamp, u32 seq<<1|lit)
mt_reply:
    .byte 0xc4, PAYLOAD_BYTES       @ BIN8 length 148
    .space PAYLOAD_BYTES
.align 2
.ltorg
