@ METRO-TAPSYNC-R02B1-SPI-CANARY (2026-11-20): M4 TX SPI frame diagnostic.
@ R01 froze M4 controls on BPM adjustment because the timing callback called
@ locking app-param/settings functions and executed VFP instructions.
@
@ R02B1 beat and bypass hooks still execute only integer loads/stores;
@ the read-only USB diagnostics run separately on HX Edit's normal UI service.
@ Extra hooks stamp a short canary and the current event counters in unused
@ tail words of small SPI TX frames and read probe values echoed by the SHARC.
@ No stock frame payload or header is overwritten; long frames are skipped.
@ All callbacks are bounded, integer-only and never call lock-taking APIs.
.syntax unified
.thumb
.include "usb.inc"
.equ REGISTER,     0x28e165f1    @ (command, &{handler, check, 0})
.equ NO_PARAMS,    0x28e19205    @ second command callback
.equ REPLY_SEND,   0x28e15b31    @ (stream, seq, status, data, [sp] data bytes)
.equ FS_STATE,     0x28d9607d    @ original stock TAP callback (must preserve result)
.equ METRO_GRID_41C, 8          @ block slot 7 on 41C is DSP grid position 8
.equ REPLY_BYTES,  34          @ MessagePack BIN8 32-byte payload + 2-byte header
.equ SPI_MAGIC,    0xFACEF00D
.equ SPI_TRAILER,  0xD00FECAF
.equ TX_CANARY,    0x4D543242  @ "B2TM" little-endian, R02B1 frame marker
.equ MAX_PAYLOAD,  230         @ avoid touching any frame whose messages approach reserved tail

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
    cmp r6, #32
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
    .word 0                     @ beat-on events seen by M4
    .word 0                     @ grid-8 metronome re-enable events
    .word 0                     @ TX frames stamped
    .word 0                     @ TX frames skipped (large/invalid)
    .word 0                     @ GR-marked DSP RX frames seen
    .word 0                     @ DSP RX word220 probe (raw halfword-swapped)
    .word 0                     @ DSP RX word221 probe (raw halfword-swapped)
    .word 0x31423252            @ LE "R2B1": exact image signature
@ Before the stock DSP->M4 receive callback, which owns SPI RX DMA frames.
@ Captures the diagnostic 220/221 words the SHARC puts in an outgoing frame.
@ This hook only reads the four words and touches its own counters.
.thumb_func
mp_rx_probe:                     @ r0=stream ctx, r1=256-word RX frame
    push {r4, r5, lr}
    ldr.w r2, [r1, #800]         @ GR word200 magic is halfword-swapped on M4
    ldr r3, =0xF00D600D
    cmp r2, r3
    bne mp_rx_done
    adr.w r4, mp_counters
    ldr r2, [r4, #16]
    adds r2, #1
    str r2, [r4, #16]
    ldr.w r2, [r1, #880]         @ SHARC word220: candidate SPI RX slot A
    str r2, [r4, #20]
    ldr.w r2, [r1, #884]         @ SHARC word221: candidate SPI RX slot B
    str r2, [r4, #24]
mp_rx_done:
    pop {r4, r5, pc}

@ After the original M4 SPI TX callback 0x10000e95 has completed constructing
@ a frame. The original TX function writes its header/trailer to r1 and may
@ fill a variable number of payload words; leave its packet untouched above
@ MAX_PAYLOAD. Slot 240..243 are unused only under that payload bound.
.thumb_func
mp_tx_stamp:                     @ r0=stream ctx, r1=256-word TX frame
    push {r4-r6, lr}
    adr.w r4, mp_counters
    ldr r2, [r1]
    ldr r3, =SPI_MAGIC
    cmp r2, r3
    bne mp_tx_skip
    ldr.w r2, [r1, #1020]
    ldr r3, =SPI_TRAILER
    cmp r2, r3
    bne mp_tx_skip
    ldr r2, [r1, #4]
    uxth r2, r2
    cmp r2, #MAX_PAYLOAD
    bhi mp_tx_skip
    movs r3, #0
    str.w r3, [r1, #960]        @ invalidate marker first
    ldr r5, [r4]
    ldr r6, [r4, #4]
    str.w r5, [r1, #964]        @ word241: TAP counter
    str.w r6, [r1, #968]        @ word242: re-enable counter
    eors r5, r6
    ldr r2, =TX_CANARY
    eors r5, r2
    mvns r5, r5
    str.w r5, [r1, #972]        @ word243: integrity check
    str.w r2, [r1, #960]        @ word240: marker committed LAST
    ldr r2, [r4, #8]
    adds r2, #1
    str r2, [r4, #8]
    b mp_tx_done
mp_tx_skip:
    ldr r2, [r4, #12]
    adds r2, #1
    str r2, [r4, #12]
mp_tx_done:
    pop {r4-r6, pc}

mp_reply:
    .byte 0xc4, 32              @ MessagePack bin8 length 32
    .space 32
.align 2
.ltorg
