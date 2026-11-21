@ METRO-LEDSYNC-R03C-HWGLITCH-REPAIR, exact installed HXtra v1.2.1 donor hooks.
@ New post-filter FS3 LED egress + 20ms OFF->ON perception filter.
@ Native stock M4 microsecond clock; no VFP, no locks, no settings writes.
@ Full 32bit counter+complement with 4600-TX-frame TAP-loss debounce.
@ In-place 142-word SHARC kernel crosschecked separately.
@ All device experiments RAM-only. On-device startup/sync NOT yet verified.
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
.equ REPLY_BYTES,  86          @ MessagePack bin8 84-byte M4-only telemetry          @ MessagePack BIN8 48-byte payload + 2-byte header
.equ SPI_MAGIC,    0xFACEF00D
.equ SPI_TRAILER,  0xD00FECAF
.equ TX_CANARY,    0x4D543242  @ "B2TM" little-endian, R02B1 frame marker
.equ TIME_US,      0x28da6459  @ stock 1-us timer
.equ MIN_VISIBLE_DARK_US, 20000
.equ MAX_PAYLOAD,  230
.equ NO_TAP_GRACE_FRAMES, 4600         @ avoid touching any frame whose messages approach reserved tail

.thumb_func
mp_led_capture:                      @ r0=FS LED index, r1=final visible RGB
    push {r4-r8, lr}                 @ 24 bytes; caller aligns stack for timer
    cmp r0, #2
    bne mp_led_capture_done
    ldr r4, =FS3_FUNCTION
    ldrb r4, [r4]
    cmp r4, #1
    bne mp_led_not_tap
    adr.w r4, mp_led_lit
    ldr r5, [r4]
    cmp r1, #0
    beq mp_led_dark
    cmp r5, #0
    bne mp_led_capture_done
    movs r5, #1
    str r5, [r4]                     @ new final LED ON command
    ldr r7, =TIME_US
    blx r7                           @ exact stock tap microsecond clock
    mov r8, r0                       @ native M4 timestamp of LED ON
    adr.w r4, mp_dark_seen
    ldr r5, [r4]
    cmp r5, #0
    beq mp_led_confirmed_on
    adr.w r4, mp_last_dark_us
    ldr r5, [r4]
    subs r0, r0, r5                 @ unsigned modulo 32bit microsecond delta
    ldr r6, =MIN_VISIBLE_DARK_US
    cmp r0, r6
    bhs mp_led_confirmed_on
    adr.w r4, mp_counters
    ldr r5, [r4, #16]              @ filtered short OFF-to-ON reversals
    adds r5, #1
    str r5, [r4, #16]
    b mp_led_capture_done
mp_led_confirmed_on:
    adr.w r4, mp_active
    ldr r5, [r4]
    cmp r5, #0
    beq mp_led_capture_done        @ bypassed Metronome remains quiet
    adr.w r6, mp_last_led_us
    str r8, [r6]                   @ accepted LED ON timestamp, before original driver
    adr.w r4, mp_counters
    ldr r5, [r4]                   @ counted physical LED flashes
    adds r5, #1
    cmp r5, #0                     @ skip zero at rare 32-bit wrap
    bne mp_led_nonzero
    movs r5, #1
mp_led_nonzero:
    str r5, [r4]
    adr.w r4, mp_reset_pending
    ldr r5, [r4]
    cmp r5, #0
    beq mp_led_capture_done
    movs r5, #0
    str r5, [r4]
    adr.w r4, mp_counters
    ldr r5, [r4]
    eor r5, r5, #0x80000000       @ an accented new downbeat on re-engage
    str r5, [r4]
    b mp_led_capture_done
mp_led_dark:
    cmp r5, #0
    beq mp_led_capture_done       @ redundant OFF cannot reset dark epoch
    movs r5, #0
    str r5, [r4]
    ldr r7, =TIME_US
    blx r7
    adr.w r4, mp_last_dark_us
    str r0, [r4]
    adr.w r4, mp_dark_seen
    movs r5, #1
    str r5, [r4]
    b mp_led_capture_done
mp_led_not_tap:
    adr.w r4, mp_led_lit
    movs r5, #0
    str r5, [r4]
    adr.w r4, mp_dark_seen
    str r5, [r4]                   @ next TAP ON begins a new epoch
mp_led_capture_done:
    pop {r4-r8, pc}

.thumb_func
.global mp_led_entry
mp_led_entry:
    push {r0-r4, lr}
    mov r4, sp
    and.w r4, r4, #7              @ donor LED callback may enter SP mod8=4
    cbz r4, mp_led_stack_ok
    sub sp, #4
mp_led_stack_ok:
    bl mp_led_capture
    cmp r4, #0
    beq mp_led_stack_restored
    add sp, #4
mp_led_stack_restored:
    pop {r0-r4, lr}
    sub sp, #20                   @ EXACT donor displaced instructions
    ldrb r2, [r3, #0]
    ldr r12, =LED_SEND_CONT
    bx r12

.thumb_func
mp_bypass:                         @ donor: engine r0, grid r1, bypass r2
    cmp r1, #METRO_GRID_41C
    bne mp_bypass_done
    adr.w r0, mp_active
    cmp r2, #0
    bne mp_bypass_off
    ldr r3, [r0]
    cmp r3, #0
    bne mp_bypass_done           @ redundant enable must NOT reset accent
    movs r3, #1
    str r3, [r0]
    str r3, [r0, #4]             @ next visible edge is downbeat
    adr.w r0, mp_counters
    ldr r3, [r0, #4]
    adds r3, #1
    str r3, [r0, #4]
    b mp_bypass_done
mp_bypass_off:
    movs r3, #0
    str r3, [r0]
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
    cmp r6, #84
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
    .word 0                      @ 0: published LED event + epoch bit31
    .word 0                      @ 1: verified engage transitions
    .word 0                      @ 2: valid SPI TX frames
    .word 0                      @ 3: skipped SPI frames
    .word 0                      @ 4: short dark->ON reversals filtered
    .word 0                      @ 5: filtered/disabled TX frames
    .word 0                      @ 6: last written SPI event word240
    .word 0                      @ 7: last written SPI integrity word241
    .word 0                      @ 8: held valid packets during transient TAP loss
    .word 0                      @ 9: explicit local fallback frames after grace
    .word 0                      @ 10: current consecutive not-TAP frames
    .word 0x31433352             @ 11: diagnostics little-endian "R3C1"
mp_led_lit:
    .word 0                      @ final LED prior bus state
mp_active:
    .word 1                      @ allow already engaged metronome at RAM boot
mp_reset_pending:
    .word 1                      @ first visible LED pulse resets accent
mp_last_dark_us:
    .word 0                      @ native microsecond timer, modulo 2^32
mp_dark_seen:
    .word 0                      @ no valid OFF timestamp before first ON
mp_no_tap_streak:
    .word 4600                   @ initial local fallback unless already in TAP
mp_last_led_us:
    .word 0                      @ M4 native 1us timestamp for accepted LED ON
mp_last_sent_event:
    .word 0                      @ latest event delivered to M4 SPI TX callback
mp_last_led_to_tx_us:
    .word 0                      @ native timestamp difference of LED to first TX stamp

@ After the *original* M4 SPI callback builds a 256-word TX frame,
@ replace only unused words240/241 when the payload is bounded <=230.
@ Valid pair is (u32 event, ~event), written integrity first, event last.
@ Zero event with ~zero is a valid idle packet suppressing local SHARC click.
@ Transient FS3 TAP mode/LED visibility losses hold a checked pair for up to
@ 4600 TX frames; persistent non-TAP publishes (0,0) to allow local Time.
.thumb_func
mp_tx_stamp:
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
    cmp r2, #1
    bne mp_tx_no_tap
    ldr r2, =TAP_LED_VISIBLE
    ldrb r2, [r2]
    cmp r2, #0
    beq mp_tx_no_tap
    adr.w r2, mp_no_tap_streak
    movs r3, #0
    str r3, [r2]
    str r3, [r4, #40]             @ 10: current not-TAP streak = 0
mp_tx_valid:
    movs r3, #0
    str.w r3, [r1, #960]         @ transient invalidation BEFORE complement
    ldr r5, [r4]
    mvn r6, r5
    str.w r6, [r1, #964]
    dmb
    str.w r5, [r1, #960]         @ publish 32-bit count last
    str r5, [r4, #24]           @ editor diagnostics
    str r6, [r4, #28]
    ldr r2, [r4, #8]
    adds r2, #1
    str r2, [r4, #8]
    adr.w r2, mp_last_sent_event
    ldr r3, [r2]
    cmp r3, r5
    beq mp_tx_done
    str r5, [r2]                   @ new event arrived at stock SPI TX stage
    ldr r6, =TIME_US
    blx r6                          @ native clock, only once per physical beat
    adr.w r2, mp_last_led_us
    ldr r3, [r2]
    subs r0, r0, r3                @ modulo-32 timestamp difference, microseconds
    adr.w r2, mp_last_led_to_tx_us
    str r0, [r2]                   @ expose via read-only editor cmd 0x50
    b mp_tx_done
mp_tx_no_tap:
    ldr r2, [r4, #20]           @ count all non-TAP/hidden LED frames
    adds r2, #1
    str r2, [r4, #20]
    adr.w r2, mp_no_tap_streak
    ldr r3, [r2]
    ldr r5, =NO_TAP_GRACE_FRAMES
    cmp r3, r5
    bhs mp_tx_explicit_fallback
    adds r3, #1
    str r3, [r2]
    str r3, [r4, #40]          @ current streak, read-only diagnostic
    ldr r2, [r4, #32]          @ held valid frame counter
    adds r2, #1
    str r2, [r4, #32]
    b mp_tx_valid              @ preserve full 2-word valid pair during dropout
mp_tx_explicit_fallback:
    movs r3, #0
    str.w r3, [r1, #960]
    str.w r3, [r1, #964]       @ explicit original donor free-running Time
    ldr r2, [r4, #36]
    adds r2, #1
    str r2, [r4, #36]
mp_tx_skip:
    ldr r2, [r4, #12]
    adds r2, #1
    str r2, [r4, #12]
mp_tx_done:
    pop {r4-r6, pc}

mp_reply:
    .byte 0xc4, 84              @ MessagePack bin8 length 84
    .space 84
.align 2
.ltorg
