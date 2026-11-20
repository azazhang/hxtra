@ METRO-LEDSYNC-R02C-DONOR-EGRESS: actual LED-send-path event capture.
@ Direct-patch the exact installed HXtra v1.2.1 donor. Preserve all donor features.
@ Capture FS3 LED dark->lit commands after HXtra's BPM LED visibility filter;
@ the M4 beat-clock callback runs BEFORE this physical output path.
@ All callbacks bounded integer-only, without locks, settings reads or VFP.
@
@ R02B2 beat and bypass hooks retain bounded integer-only event capture;
@ the read-only USB diagnostics run separately on HX Edit's normal UI service.
@ Extra hooks stamp a short canary and the current event counters in unused
@ tail words of small SPI TX frames and read probe values echoed by the SHARC.
@ LED egress is reached through donor 0x28d98f78 after bpm_ledsend.
@ The 4 overwritten Thumb bytes are reproduced before the tail continuation;
@ original Tap Command/BPM/Tuner and all other donor code are unchanged.
@ TX and RX existing callbacks are wrapped, never overwritten.
@ Actual light emission may follow the bus command by panel-controller latency.
@ All callbacks are bounded, integer-only and never call lock-taking APIs.
.syntax unified
.thumb
.include "usb.inc"
.equ REGISTER,     0x28e165f1    @ (command, &{handler, check, 0})
.equ NO_PARAMS,    0x28e19205    @ second command callback
.equ REPLY_SEND,   0x28e15b31    @ (stream, seq, status, data, [sp] data bytes)
.equ LED_SEND_CONT, 0x28d98f7d @ original low-level sender after displaced instructions
.equ FS3_FUNCTION, 0x28128a78 @ donor footswitch #3 function byte: 1 = TAP
.equ TAP_LED_VISIBLE, 0x28e4daee @ exact installed bpm_ledsend tap visibility byte
.equ METRO_GRID_41C, 8          @ block slot 7 on 41C is DSP grid position 8
.equ REPLY_BYTES,  50          @ MessagePack BIN8 48-byte payload + 2-byte header
.equ SPI_MAGIC,    0xFACEF00D
.equ SPI_TRAILER,  0xD00FECAF
.equ TX_CANARY,    0x4D543242  @ "B2TM" little-endian, R02B1 frame marker
.equ MAX_PAYLOAD,  230         @ avoid touching any frame whose messages approach reserved tail

.thumb_func
mp_led_capture:                   @ r0=LED index, r1=FINAL colour AFTER donor filter
    cmp r0, #2                   @ only physical FS3 ring
    bne mp_led_capture_done
    ldr r2, =FS3_FUNCTION
    ldrb r2, [r2]
    cmp r2, #1                   @ FS3 must actually be TAP, not Preset/Snapshot
    bne mp_led_not_tap
    adr.w r2, mp_led_lit
    ldr r3, [r2]                @ last requested bus state: 0 dark, 1 lit
    cmp r1, #0
    beq mp_led_dark
    cmp r3, #0
    bne mp_led_capture_done     @ red->other colour without off = same flash
    movs r3, #1
    str r3, [r2]
    adr.w r2, mp_active
    ldr r3, [r2]
    cmp r3, #0
    beq mp_led_capture_done     @ do not publish rising edges while 41C bypassed
    adr.w r2, mp_counters
    ldr r3, [r2]
    adds r3, #1
    str r3, [r2]                @ one event per actual bus dark->lit edge
    adr.w r2, mp_reset_pending
    ldr r3, [r2]
    cmp r3, #0
    beq mp_led_capture_done
    movs r3, #0
    str r3, [r2]               @ consume pending reset on this *visible* edge
    adr.w r2, mp_counters
    ldr r3, [r2]
    eor r3, r3, #0x80000000    @ SHARC identifies bar-reset at next flash
    str r3, [r2]
    b mp_led_capture_done
mp_led_not_tap:
    adr.w r2, mp_led_lit
mp_led_dark:
    movs r3, #0
    str r3, [r2]                @ reset state when FS3 changes function
mp_led_capture_done:
    bx lr

.thumb_func
.global mp_led_entry
mp_led_entry:                     @ direct donor hook 0x28d98f78
    push {r0-r4, lr}
    bl mp_led_capture            @ r1 already passed donor's Tap-LED Off filter
    pop {r0-r4, lr}
    sub sp, #20                  @ reproduce the displaced donor Thumb instructions
    ldrb r2, [r3, #0]
    ldr r12, =LED_SEND_CONT
    bx r12                       @ resume the original LED serializer

.thumb_func
mp_bypass:                       @ after original bypass setter, args r0 engine, r1 grid, r2 bypass
    cmp r1, #METRO_GRID_41C
    bne mp_bypass_done
    adr.w r0, mp_active
    cmp r2, #0
    bne mp_bypass_off
    movs r3, #1
    str r3, [r0]               @ active from the original donor bypass transition
    str r3, [r0, #4]           @ next *LED-on* event must reset accent
    adr.w r0, mp_counters
    ldr r3, [r0, #4]
    adds r3, #1
    str r3, [r0, #4]
    b mp_bypass_done
mp_bypass_off:
    movs r3, #0
    str r3, [r0]               @ published LED event count freezes during bypass
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
    add r5, #2                  @ the 48 payload bytes, after BIN8 header
    movs r6, #0
mp_copy:
    ldrb r0, [r4, r6]
    strb r0, [r5, r6]
    adds r6, #1
    cmp r6, #48
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
    .word 0                     @ DSP RX word220: SHARC-observed M4 TX marker
    .word 0                     @ DSP RX word221: SHARC-observed TAP event count
    .word 0                     @ DSP RX word222: SHARC-observed metronome re-enable count
    .word 0                     @ DSP RX word223: SHARC-observed integrity checksum
    .word 0                     @ confirmed valid echoed event frames
    .word 0                     @ echoed marker-present frames failing checksum
    .word 0x43324352            @ LE "RC2C": donor-direct diagnostic signature
mp_led_lit:
    .word 0                     @ preceding bus state, zero or nonzero
mp_active:
    .word 1                     @ allow already-engaged metronome on RAM start
mp_reset_pending:
    .word 1                     @ first real visible LED rise is the accented downbeat
@ Before the stock DSP->M4 receive callback. SHARC mirrors TX words 240..243
@ to its return-frame words 220..223. Snapshot four echoed values and check
@ the marker / 32-bit XOR complement without any locks or runtime API calls.
.thumb_func
mp_rx_probe:                     @ r0=stream ctx, r1=256-word RX frame
    push {r4-r6, lr}
    ldr.w r2, [r1, #800]         @ GR frame word200, as M4 receives it
    ldr r3, =0xF00D600D
    cmp r2, r3
    bne mp_rx_done
    adr.w r4, mp_counters
    ldr r2, [r4, #16]
    adds r2, #1
    str r2, [r4, #16]
    ldr.w r2, [r1, #880]         @ DSP echo word220: M4 TX marker
    str r2, [r4, #20]
    ldr.w r5, [r1, #884]         @ DSP echo word221: M4 TAP count
    str r5, [r4, #24]
    ldr.w r6, [r1, #888]         @ DSP echo word222: M4 re-enable count
    str r6, [r4, #28]
    ldr.w r3, [r1, #892]         @ DSP echo word223: M4 integrity check
    str r3, [r4, #32]
    ldr r1, =TX_CANARY
    cmp r2, r1
    bne mp_rx_done
    eors r5, r6
    eors r5, r2
    mvns r5, r5
    cmp r5, r3
    bne mp_rx_bad
    ldr r2, [r4, #36]
    adds r2, #1
    str r2, [r4, #36]
    b mp_rx_done
mp_rx_bad:
    ldr r2, [r4, #40]
    adds r2, #1
    str r2, [r4, #40]
mp_rx_done:
    pop {r4-r6, pc}

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
    ldr r2, =FS3_FUNCTION
    ldrb r2, [r2]
    cmp r2, #1                  @ non-TAP FS3: use the donor's local metronome
    bne mp_tx_no_tap
    ldr r2, =TAP_LED_VISIBLE
    ldrb r2, [r2]               @ installed bpm_ledsend post-filter visibility state
    cmp r2, #0
    beq mp_tx_no_tap            @ invisible TAP: original donor local click continues
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
mp_tx_no_tap:
    movs r3, #0
    str.w r3, [r1, #960]       @ invalidate marker: SHARC falls back to donor click
mp_tx_skip:
    ldr r2, [r4, #12]
    adds r2, #1
    str r2, [r4, #12]
mp_tx_done:
    pop {r4-r6, pc}

mp_reply:
    .byte 0xc4, 48              @ MessagePack bin8 length 48
    .space 48
.align 2
.ltorg
