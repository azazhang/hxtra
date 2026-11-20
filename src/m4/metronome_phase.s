@ METRO-TAPSYNC-R02A-M4EDGE (2026-11-20): M4 event-capture diagnostic.
@ R01 froze M4 controls on BPM adjustment because the timing callback called
@ locking app-param/settings functions and executed VFP instructions.
@
@ R02A beat and bypass hooks execute only bounded integer loads/stores;
@ the read-only USB diagnostics run separately on HX Edit's normal UI service.
@ No DSP event transmission in this revision: counters first establish that
@ the hooks execute and the interface remains responsive under BPM changes.
.syntax unified
.thumb
.include "usb.inc"
.equ REGISTER,     0x28e165f1    @ (command, &{handler, check, 0})
.equ NO_PARAMS,    0x28e19205    @ second command callback
.equ REPLY_SEND,   0x28e15b31    @ (stream, seq, status, data, [sp] data bytes)
.equ FS_STATE,     0x28d9607d    @ original stock TAP callback (must preserve result)
.equ METRO_GRID_41C, 8          @ block slot 7 on 41C is DSP grid position 8
.equ REPLY_BYTES,  14          @ MessagePack BIN8 12-byte payload + 2-byte header

.thumb_func
mp_beat:                         @ replaces stock FS_STATE call during LED ON event
    push {r4, lr}
    ldr r3, =FS_STATE
    blx r3                      @ exact original operation
    mov r4, r0
    adr.w r1, mp_counters
    ldr r2, [r1]                @ atomic aligned 32-bit counter
    adds r2, #1
    str r2, [r1]
    mov r0, r4                  @ original return value, same calling convention
    pop {r4, pc}

.thumb_func
mp_bypass:                       @ after original bypass setter, args r0 engine, r1 grid, r2 bypass
    cmp r1, #METRO_GRID_41C
    bne mp_bypass_done
    cmp r2, #0                  @ bypass -> active
    bne mp_bypass_done
    adr.w r0, mp_counters
    ldr r3, [r0, #4]
    adds r3, #1
    str r3, [r0, #4]
mp_bypass_done:
    bx lr

.thumb_func
mp_register:                     @ once, after editor command registrations (UI setup context)
    push {r4, lr}
    sub sp, #16
    adr.w r0, mp_command
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
mp_command:                      @ read-only editor command on regular UI service thread
    push {r4-r8, lr}
    sub sp, #8                  @ 8-byte stack alignment, SEND length at [sp]
    mov r7, r0                  @ stream
    ldrh r8, [r1, #0xc]         @ sequence ID
    adr.w r4, mp_counters
    adr.w r5, mp_reply
    add r5, #2                  @ the 12 payload bytes, after BIN8 header
    movs r6, #0
mp_copy:
    ldrb r0, [r4, r6]
    strb r0, [r5, r6]
    adds r6, #1
    cmp r6, #12
    blo mp_copy
    movs r0, #REPLY_BYTES
    str r0, [sp]
    mov r0, r7
    mov r1, r8
    movs r2, #0
    adr.w r3, mp_reply
    ldr r12, =REPLY_SEND
    blx r12
    add sp, #8
    pop {r4-r8, pc}

.align 2
mp_counters:
    .word 0                     @ beat-on events seen by M4 (u32 little-endian)
    .word 0                     @ grid-8 metronome re-enable events (u32 little-endian)
    .word 0x52303241            @ ASCII 'A20R', R02A diagnostic version sentinel
mp_reply:
    .byte 0xc4, 12              @ MessagePack bin8 length 12
    .space 12
.align 2
.ltorg
