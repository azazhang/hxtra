#!/usr/bin/env python3
"""Derive the M4 LED master from the pinned exact-donor R02C transport hooks.

R03B uses the verified R01 post-filter FS3 LED egress and original M4
microsecond timer, a 20 ms dark-gap suppression informed by physical
HWKNOB01 short OFF/ON intervals, and a two-word complement-checked SPI
publication at TX 240/241. It retains donor bypass behavior, functions,
DSP feature menu, and the separate read-only editor diagnostic.
This file builds source only: NO device access, flashing, or RUN.
"""
from pathlib import Path
import subprocess,hashlib
ROOT=Path(__file__).resolve().parents[1]
SOURCE_REV='ace7026'
SOURCE_PATH='src/m4/metronome_led_egress.s'
DEST=ROOT/'src/m4/metronome_led_r03b.s'

LED_CAPTURE='''.thumb_func
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

'''

BYPASS='''.thumb_func
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

'''

STATE='''.align 2
mp_counters:
    .word 0                      @ 0: published LED event + epoch bit31
    .word 0                      @ 1: verified engage transitions
    .word 0                      @ 2: valid SPI TX frames
    .word 0                      @ 3: skipped SPI frames
    .word 0                      @ 4: short dark->ON reversals filtered
    .word 0                      @ 5: filtered/disabled TX frames
    .word 0                      @ 6: last written SPI event word240
    .word 0                      @ 7: last written SPI integrity word241
    .word 0                      @ 8: reserved
    .word 0                      @ 9: reserved
    .word 0                      @ 10: reserved
    .word 0x31423352             @ 11: diagnostics little-endian "R3B1"
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

'''

TX='''@ After the *original* M4 SPI callback builds a 256-word TX frame,
@ replace only unused words240/241 when the payload is bounded <=230.
@ Valid pair is (u32 event, ~event), written integrity first, event last.
@ Zero event with ~zero is a valid idle packet suppressing local SHARC click.
@ When TAP is unavailable/invisible, both words are 0: explicitly re-enable
@ the original local donor metronome in the R03B SHARC kernel.
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
    b mp_tx_done
mp_tx_no_tap:
    movs r3, #0
    str.w r3, [r1, #960]
    str.w r3, [r1, #964]        @ explicit local fallback (0,0)
    ldr r2, [r4, #20]
    adds r2, #1
    str r2, [r4, #20]
mp_tx_skip:
    ldr r2, [r4, #12]
    adds r2, #1
    str r2, [r4, #12]
mp_tx_done:
    pop {r4-r6, pc}

'''

def build():
    text=subprocess.check_output(['git','show',f'{SOURCE_REV}:{SOURCE_PATH}'],cwd=ROOT,text=True)
    a=text.index('@ METRO-LEDSYNC-R02C-DONOR-EGRESS:')
    b=text.index('.syntax unified')
    header="""@ METRO-LEDSYNC-R03B-LED-MASTER, exact installed HXtra v1.2.1 donor hooks.
@ New post-filter FS3 LED egress + 20ms OFF->ON perception filter.
@ Native stock M4 microsecond clock; no VFP, no locks, no settings writes.
@ Full 32bit M4->SHARC SPI event+bitwise complement, TX words240/241.
@ In-place 142-word SHARC kernel crosschecked separately.
@ All device experiments RAM-only. On-device startup/sync NOT yet verified.
"""
    text=header+text[b:]
    text=text.replace('.equ MAX_PAYLOAD,  230', '.equ TIME_US,      0x28da6459  @ stock 1-us timer\n.equ MIN_VISIBLE_DARK_US, 20000\n.equ MAX_PAYLOAD,  230')
    a=text.index('.thumb_func\nmp_led_capture:')
    b=text.index('.thumb_func\nmp_bypass:')
    text=text[:a]+LED_CAPTURE+text[b:]
    a=text.index('.thumb_func\nmp_bypass:')
    b=text.index('.thumb_func\nmp_register:')
    text=text[:a]+BYPASS+text[b:]
    a=text.index('.align 2\nmp_counters:')
    b=text.index('@ After the original M4 SPI TX callback')
    text=text[:a]+STATE+text[b:]
    a=text.index('@ After the original M4 SPI TX callback')
    b=text.index('mp_reply:')
    text=text[:a]+TX+text[b:]
    assert '.thumb_func\nmp_rx_probe:' not in text
    assert text.count('mp_led_entry:')==1 and text.count('mp_tx_stamp:')==1
    assert 'mp_led_stack_ok' in text
    DEST.write_text(text)
    return text

if __name__=='__main__':
    text=build()
    print(str(DEST), 'sha256',hashlib.sha256(text.encode()).hexdigest())
