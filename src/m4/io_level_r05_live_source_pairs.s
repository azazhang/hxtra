@ IO-LEVEL-R05: two horizontal live bars from the verified native R01
@ 44-word / eight-record SHARC-to-M4 meter events.
@ Built on exact flashed R03C, preserving R01 read-only frame command 0x4f.
@ All DSP entries byte-identical. Native event group assignment:
@ first L/R pair -> LEFT trial bar; last L/R pair -> RIGHT trial bar.
@ Signal-path identity remains pending controlled physical amplitude testing.
@ R05 is an opt-in user-initiated RAM prototype, NOT updater-ready.
.syntax unified
.thumb
@ The original R01 0x4F raw frame command is unchanged. 0x13 only
@ returns rolling summary data captured by this module, without changing
@ device configuration, DSP, audio routing or metronome state.
.equ MTR_CMD,       0x13
.equ MTR_REGISTER,  0x28e165f1
.equ MTR_NO_PARAMS, 0x28e19205
.equ MTR_REPLY,     0x28e15b31
.equ MTR_REPLY_N,   643         @ 640-byte BIN16 body + 3 prefix bytes
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
    mov r0, r4
    bl io_capture_native_events        @ capture ALL complete records, any packet length
    ldr.w r2, [r4, #4]
    lsrs r2, #16
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

    @ R05: full 44-word bulk frames still update read-only diagnostics,
    @ but the Home bars use distinct incrementally reported native keys
    @ proved responsive in R04 HW01/HW02/HW03. Do not overwrite them here.
    b io_meter_done

io_no_update:
    b io_meter_done

@ Per-source stale expiry is independent. At ~2300 RX frames/s,
@ 4600 ticks is ~2 s. If one candidate stops sending, the other remains
@ live. Repaint from RX at <= roughly 23 Hz (100 callbacks), independent
@ of how frequently either native key changes; no UI draw in IRQ inner loop.
io_meter_done:
    adr.w r6, io_live_ages
    movw r8, #R02_TTL
    movs r7, #0
io_age_loop:
    ldr r2, [r6]
    cmp r2, r8
    bhs io_age_next
    adds r2, #1
    str r2, [r6]
    cmp r2, r8
    bne io_age_next
    adr.w r4, io_bar_state
    ldr r5, [r4]
    mov r0, r5
    cbnz r7, io_age_clear_right
    bic.w r5, r5, #0x000000ff
    b io_age_changed
io_age_clear_right:
    bic.w r5, r5, #0x0000ff00
io_age_changed:
    cmp r5, r0
    beq io_age_next
    str r5, [r4]
    adr.w r4, io_diag_live
    str r5, [r4, #24]
    ldr r2, [r4, #20]
    adds r2, #1
    str r2, [r4, #20]
    adr.w r4, io_redraw_pending
    movs r2, #1
    str r2, [r4]
io_age_next:
    adds r6, #4
    adds r7, #1
    cmp r7, #2
    bne io_age_loop

    adr.w r6, io_redraw_tick
    ldr r2, [r6]
    adds r2, #1
    str r2, [r6]                  @ persist EVERY RX tick before throttle branch
    cmp r2, #100
    blo io_meter_exit
    movs r2, #0
    str r2, [r6]
    adr.w r6, io_redraw_pending
    ldr r2, [r6]
    cbz r2, io_meter_exit
    movs r2, #0
    str r2, [r6]
    movs r0, #0
    movs r1, #1
    ldr r3, =UI_REDRAW
    blx r3
io_meter_exit:
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
    .word 0                          @ retained R03/R04 state padding (unused TTL)
io_live_ages:
    .word 0                          @ age since last Guitar/Input candidate event
    .word 0                          @ age since last Main/Output candidate event
io_redraw_tick:
    .word 0                          @ RX callbacks until next UI redraw opportunity
io_redraw_pending:
    .word 0                          @ coalesce source changes until redraw
@ Every SHARC->M4 native packet can contain 0..N complete five-word
@ update events. R02/R03 filtered only 44-word bulk frames, discarding
@ >99% of actual nonempty messages (verified on hardware). This stores
@ a bounded ledger keyed by [object_id, parameter_id] without assuming
@ which event relates to Guitar In or Main Out. There are 24 slots, each
@ 24 bytes: raw 16bit-swapped family, raw param, last, count, min, max.
@ Values are exact floats from native records; min/max use IEEE total
@ order for finite float32. No SHARC or permanent settings are changed.
.thumb_func
io_capture_native_events:             @ r0 frame address; all registers saved
    push {r4-r11, lr}
    mov r4, r0
    ldr r5, [r4]
    ldr r6, =RX_MAGIC
    cmp r5, r6
    bne io_events_done
    ldr.w r5, [r4, #1020]
    ldr r6, =RX_END
    cmp r5, r6
    bne io_events_done
    ldr.w r5, [r4, #4]
    lsrs r5, #16                    @ payload word count
    cmp r5, #9                      @ four-word envelope and one full record
    blo io_events_done
    cmp r5, #244                    @ refuse out-of-bounds payload
    bhi io_events_done
    ldr.w r6, [r4, #8]
    ror.w r6, r6, #16               @ packet envelope native word 0
    lsrs r7, r6, #24
    cmp r7, #0x18
    bne io_events_done
    uxth r6, r6
    subs r7, r5, #2
    lsls r7, r7, #2
    cmp r6, r7                     @ native payload byte length
    bne io_events_done
    ldr.w r6, [r4, #12]
    ldr r7, =RX44_FLAGS
    cmp r6, r7
    bne io_events_done
    subs r5, #4
    movs r6, #5
    udiv r5, r5, r6                @ full five-word native events, ignore tail
    cbz r5, io_events_done
    add.w r6, r4, #24              @ start raw word6
    adr.w r8, io_event_seq
    ldr r0, [r8]
    adds r0, #1
    str r0, [r8]                   @ odd = in-progress writer
io_events_loop:
    ldr.w r0, [r6]                 @ native record magic/part 0
    cmp r0, #0
    bne io_events_next
    ldr.w r0, [r6, #4]             @ native record type 3
    ldr r1, =0x00030000
    cmp r0, r1
    bne io_events_next
    ldr.w r9, [r6, #8]             @ raw halfword-swapped object family
    uxth r0, r9
    cmp r0, #2                     @ only verified 0x0002xxxx family
    bne io_events_next
    ldr.w r10, [r6, #12]           @ raw halfword-swapped parameter id
    uxth r0, r10
    cmp r0, #0
    bne io_events_next             @ high halfword must be the parameter id
    ldr.w r11, [r6, #16]           @ float32 raw halfword-swapped value
    ror.w r0, r11, #16
    ubfx r1, r0, #23, #8
    cmp r1, #255
    beq io_events_next             @ ignore NaNs/infinities in ledger
    mov r0, r9
    mov r1, r10
    mov r2, r11
    bl io_record_event
io_events_next:
    adds r6, #20
    subs r5, #1
    bne io_events_loop
    dmb
    ldr r0, [r8]
    adds r0, #1
    str r0, [r8]                   @ even = all table fields published
io_events_done:
    pop {r4-r11, pc}

@ r0=raw family, r1=raw parameter, r2=halfword-swapped IEEE float
.thumb_func
io_record_event:
    push {r4-r8, lr}
    adr.w r4, io_event_table
    movs r5, #24                   @ at most 24 live event families/parameters
io_row_scan:
    ldr r3, [r4]
    cbz r3, io_row_new
    cmp r3, r0
    bne io_row_next
    ldr r3, [r4, #4]
    cmp r3, r1
    beq io_row_found
io_row_next:
    adds r4, #24
    subs r5, #1
    bne io_row_scan
    b io_record_exit                @ full ledger; keep existing keys stable
io_row_new:
    str r0, [r4]
    str r1, [r4, #4]
    str r2, [r4, #8]
    movs r3, #1
    str r3, [r4, #12]
    str r2, [r4, #16]
    str r2, [r4, #20]
    b io_row_done
io_row_found:
    str r2, [r4, #8]
    ldr r3, [r4, #12]
    adds r3, #1
    str r3, [r4, #12]
    mov r0, r2
    bl io_float_order
    mov r7, r0
    ldr r0, [r4, #16]
    bl io_float_order
    cmp r7, r0
    it lo
    strlo r2, [r4, #16]            @ floating point minimum (raw)
    ldr r0, [r4, #20]
    bl io_float_order
    cmp r7, r0
    it hi
    strhi r2, [r4, #20]            @ floating point maximum (raw)
io_row_done:
    @ Native object/parameter IDs from physical R04 HW03 (metronome off,
    @ guitar-only): 0x00020002/id3 fluctuates with guitar, and
    @ 0x0002002a/id1 tracks guitar plus TAP-aligned metronome pulses.
    @ They are provisional INPUT and OUTPUT candidates respectively;
    @ no stock Line6 physical-jack mapping is asserted here.
    ldr r0, [r4]                 @ as-received halfword-swapped object
    ldr r1, =0x00020002
    cmp r0, r1
    bne io_try_output
    ldr r0, [r4, #4]
    ldr r1, =0x00030000
    cmp r0, r1
    beq io_publish_input
io_try_output:
    ldr r0, [r4]
    ldr r1, =0x002a0002           @ unswapped 0x0002002a
    cmp r0, r1
    bne io_record_exit
    ldr r0, [r4, #4]
    ldr r1, =0x00010000           @ native parameter 1
    cmp r0, r1
    bne io_record_exit
    movs r6, #1
    b io_convert_bar
io_publish_input:
    movs r6, #0
io_convert_bar:
    mov r0, r2
    ror.w r0, r0, #16
    bl io_level_to_bin           @ 0..132 genuine native signal dB pixels
    adr.w r4, io_bar_state
    ldr r5, [r4]
    cbnz r6, io_set_right
    bfi r5, r0, #0, #8
    b io_publish_bar
io_set_right:
    bfi r5, r0, #8, #8
io_publish_bar:
    orr r5, r5, #0x80000000
    adr.w r0, io_live_ages
    add.w r0, r0, r6, lsl #2
    movs r3, #0
    str r3, [r0]               @ source-specific freshness
    ldr r0, [r4]
    cmp r0, r5
    beq io_record_exit
    str r5, [r4]               @ atomic two-width packed bar state
    adr.w r4, io_diag_live
    str r5, [r4, #24]
    ldr r0, [r4, #20]
    adds r0, #1
    str r0, [r4, #20]
    adr.w r4, io_redraw_pending
    movs r0, #1
    str r0, [r4]               @ deferred 23Hz max UI repaint
io_record_exit:
    pop {r4-r8, pc}

@ Return sortable unsigned key for *finite* IEEE754 float32 raw M4 word.
.thumb_func
io_float_order:
    ror.w r0, r0, #16
    lsrs r3, r0, #31
    cbz r3, io_float_positive
    mvn r0, r0
    bx lr
io_float_positive:
    eor r0, r0, #0x80000000
    bx lr

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
    push {r4-r10, lr}
    sub sp, #8
    mov r7, r0                        @ editor USB stream
    ldrh r8, [r1, #12]               @ read-only request sequence
    adr.w r4, io_diag_live
    adr.w r5, io_diag_reply_body
    adr.w r9, io_event_seq
io_diag_retry:
    ldr r6, [r9]                     @ even version before snapshot
    tst r6, #1
    bne io_diag_retry
    mov r1, r4
    mov r3, r5
    movs r2, #160                    @ 160 × 4 = 640 bytes
io_diag_copy:
    ldr.w r0, [r1], #4
    str.w r0, [r3], #4
    subs r2, #1
    bne io_diag_copy
    dmb
    ldr r0, [r9]
    cmp r0, r6
    bne io_diag_retry                @ avoid torn RX packet payload
    movw r0, #MTR_REPLY_N
    str r0, [sp]
    mov r0, r7
    mov r1, r8
    movs r2, #0
    adr.w r3, io_diag_reply_body
    subs r3, #3                      @ exact BIN16 prefix before body
    ldr r12, =MTR_REPLY
    blx r12
    add sp, #8
    pop {r4-r10, pc}

@ Published rolling native metering stats. This is only M4 RAM, and
@ 0x13 is a read-only editor command. Live fields after 0x13 packet:
@   0: ASCII IOM3; 4: RX total; 8: nonempty; 12: 44-word candidates;
@   16: accepted 44-word meter packets; 20: bar changes; 24: bar state;
@   28: native header; 32..63: eight 32bit raw meter readings;
@   64..639: up to 24 keyed records of (object, param, last, count,
@              minimum, maximum), each field uint32 / raw float bits.
@ The physically observed native packet's short incremental records
@ are included independent of the 44-word bulk packet. Each RX capture
@ begins odd and ends even version in io_event_seq; USB reads stable.
.align 2
io_diag_live:
    .word 0x344d4f49                 @ IOM4
    .space 60
io_event_table:
    .space 576                      @ 24 × 24B tracked native record keys
io_event_seq:
    .word 0                         @ odd=in-progress, even=published
    .byte 0                         @ 3-byte msgpack BIN16 before 4B body
io_diag_reply_prefix:
    .byte 0xc5, 0x02, 0x80          @ BIN16, 640-byte read-only payload
io_diag_reply_body:
    .word 0x344d4f49                 @ IOM4
    .space 636
.align 2
.ltorg
