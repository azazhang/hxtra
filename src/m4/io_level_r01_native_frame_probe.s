@ IO-LEVEL-R01: native DSP->M4 RX frame instrumentation, code-only overlay.
@ Exact tested R03C HXF remains the donor. No SHARC change whatsoever.
@ On-device M4 editor command 0x4F returns a single captured raw RX frame.
@ The stock GR handler and original RX callback are chained and untouched.
@ Nothing writes to DSP, SPI, presets, settings, USB audio or persistent flash.
.syntax unified
.thumb

.equ CMD,          0x4f
.equ REGISTER,     0x28e165f1
.equ NO_PARAMS,    0x28e19205
.equ REPLY_SEND,   0x28e15b31
.equ FRAME_MAGIC,  0xf00dface  @ 0xFACEF00D halfword-swapped at the M4 RX callback
.equ FRAME_END,    0xecafd00f  @ 0xD00FECAF halfword-swapped at the M4 RX callback
.equ REPLY_N,      1043        @ msgpack BIN16 + 16-byte header + 1024-byte SPI frame

.thumb_func
io_probe_frame:                      @ r1 = frame from SHARC; invoked before HXtra GR receiver
    push {r0-r7, lr}
    adr.w r4, io_state
    ldr r0, [r4]
    cmp r0, #1
    bne io_frame_done
    ldr r0, [r1]
    ldr r2, =FRAME_MAGIC
    cmp r0, r2
    bne io_frame_done
    ldr.w r0, [r1, #1020]
    ldr r2, =FRAME_END
    cmp r0, r2
    bne io_frame_done
    mov r5, r1
    adr.w r6, io_capture_data       @ capture writes only the back buffer
    movs r7, #0
io_copy:
    ldr.w r0, [r5, r7, lsl #2]
    str.w r0, [r6, r7, lsl #2]
    adds r7, #1
    cmp.w r7, #256
    bne io_copy
    adr.w r6, io_stats
    ldr r0, [r6]
    adds r0, #1
    str r0, [r6]                    @ captured frame count; separate from reply
    str r0, [r6, #4]                @ successful snapshots
    dmb                              @ publish completed back-buffer snapshot
    movs r0, #2
    str r0, [r4]                    @ published, prevent concurrent overwrite
io_frame_done:
    pop {r0-r7, pc}

.thumb_func
io_probe_register:
    push {r4, lr}
    sub sp, #16
    adr.w r0, io_probe_command
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

.thumb_func
io_probe_command:                    @ editor request, read-only, 1 kB frame response
    push {r4-r8, lr}
    sub sp, #8
    mov r7, r0                       @ editor stream
    ldrh r8, [r1, #12]               @ sequence number
    @ The capture state is marked 2 only *after* the full 1024-byte RX
    @ frame is written and the release barrier has executed. If no fresh
    @ complete frame is ready, keep the previous front-buffer contents.
    adr.w r4, io_state
    ldr r0, [r4]
    cmp r0, #2
    bne io_reply_send
    @ Stable reply: copy the last complete one-shot capture to a separate
    @ front buffer. The RX frame callback may never write to this buffer.
    adr.w r4, io_stats
    adr.w r5, io_reply_header
    ldr r0, [r4]
    str r0, [r5, #4]
    ldr r0, [r4, #4]
    str r0, [r5, #8]
    adr.w r4, io_capture_data
    adr.w r5, io_reply_data
    movw r6, #256
io_reply_copy:
    ldr r0, [r4], #4
    str r0, [r5], #4
    subs r6, #1
    bne io_reply_copy
io_reply_send:
    ldr r0, =REPLY_N
    str r0, [sp]
    mov r0, r7
    mov r1, r8
    movs r2, #0                      @ success status
    adr.w r3, io_reply_header
    subs r3, #3                     @ exactly 3 BIN16 bytes before aligned payload
    ldr r12, =REPLY_SEND
    blx r12
    adr.w r4, io_state
    movs r0, #1                      @ arm a new sample AFTER the stable reply
    str r0, [r4]
    add sp, #8
    pop {r4-r8, pc}

.align 2
io_state:
    .word 1                          @ capture first valid frame after startup
io_stats:
    .word 0                          @ complete captures (updated only by RX)
    .word 0                          @ valid frames (updated only by RX)
    .byte 0                          @ align the BIN16 body that follows
io_reply_prefix:
    .byte 0xc5, 0x04, 0x10          @ BIN16, big-endian payload 0x0410 bytes
io_reply_header:
    .word 0x31524f49                 @ little endian "IOR1"
    .word 0                          @ sample counter, front copy
    .word 0                          @ valid frames, front copy
    .word 0                          @ reserved
io_reply_data:
    .space 1024                     @ immutable front buffer for USB reply
io_capture_data:
    .space 1024                     @ separate RX-only back buffer
.align 2
.ltorg
