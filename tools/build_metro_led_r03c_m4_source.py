#!/usr/bin/env python3
"""R03C M4 producer from fixed R03B, with hysteresis for transient non-TAP.

R03B immediately published an invalid (0,0) SPI pair for any single frame
whose TAP assignment/LED visibility was false. The SHARC then re-enabled
its independent Time clock even if the user kept a steady tempo. Add a
short-mode dropout grace: hold the last valid counter/complement for up to
4600 consecutive SPI frames (~2s at empirically observed 2300 frames/s).
After persistent non-TAP, publish (0,0) for the original donor behavior.

Initialize consecutive count to threshold to preserve original non-TAP
behavior when the pedal first boots in preset/other FS3 mode.

Source-only builder; no device interactions, no firmware writes.
"""
from pathlib import Path
import subprocess,hashlib
ROOT=Path(__file__).resolve().parents[1]
REV='5894378'
SRC='src/m4/metronome_led_r03b.s'
DEST=ROOT/'src/m4/metronome_led_r03c.s'
THRESH=4600
def build():
    s=subprocess.check_output(['git','show',f'{REV}:{SRC}'],cwd=ROOT,text=True)
    def replace(a,b):
        nonlocal s
        assert s.count(a)==1,(a,s.count(a))
        s=s.replace(a,b)
    replace('@ METRO-LEDSYNC-R03B-LED-MASTER, exact installed HXtra v1.2.1 donor hooks.',
            '@ METRO-LEDSYNC-R03C-HWGLITCH-REPAIR, exact installed HXtra v1.2.1 donor hooks.')
    replace('@ Full 32bit M4->SHARC SPI event+bitwise complement, TX words240/241.',
            '@ Full 32bit counter+complement with 4600-TX-frame TAP-loss debounce.')
    replace('.equ MAX_PAYLOAD,  230',
            '.equ MAX_PAYLOAD,  230\n.equ NO_TAP_GRACE_FRAMES, 4600')
    replace('    .word 0                      @ 8: reserved\n    .word 0                      @ 9: reserved\n    .word 0                      @ 10: reserved\n    .word 0x31423352             @ 11: diagnostics little-endian "R3B1"',
            '    .word 0                      @ 8: held valid packets during transient TAP loss\n    .word 0                      @ 9: explicit local fallback frames after grace\n    .word 0                      @ 10: current consecutive not-TAP frames\n    .word 0x31433352             @ 11: diagnostics little-endian "R3C1"')
    replace('mp_dark_seen:\n    .word 0                      @ no valid OFF timestamp before first ON',
            'mp_dark_seen:\n    .word 0                      @ no valid OFF timestamp before first ON\nmp_no_tap_streak:\n    .word 4600                   @ initial local fallback unless already in TAP\nmp_last_led_us:\n    .word 0                      @ M4 native 1us timestamp for accepted LED ON\nmp_last_sent_event:\n    .word 0                      @ latest event delivered to M4 SPI TX callback\nmp_last_led_to_tx_us:\n    .word 0                      @ native timestamp difference of LED to first TX stamp')
    replace('    cmp r2, #0\n    beq mp_tx_no_tap\n    movs r3, #0\n    str.w r3, [r1, #960]',
            '    cmp r2, #0\n    beq mp_tx_no_tap\n    adr.w r2, mp_no_tap_streak\n    movs r3, #0\n    str r3, [r2]\n    str r3, [r4, #40]             @ 10: current not-TAP streak = 0\nmp_tx_valid:\n    movs r3, #0\n    str.w r3, [r1, #960]')
    a='''mp_tx_no_tap:
    movs r3, #0
    str.w r3, [r1, #960]
    str.w r3, [r1, #964]        @ explicit local fallback (0,0)
    ldr r2, [r4, #20]
    adds r2, #1
    str r2, [r4, #20]
mp_tx_skip:
'''
    b='''mp_tx_no_tap:
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
'''
    replace(a,b)
    replace('@ When TAP is unavailable/invisible, both words are 0: explicitly re-enable\n@ the original local donor metronome in the R03B SHARC kernel.',
            '@ Transient FS3 TAP mode/LED visibility losses hold a checked pair for up to\n@ 4600 TX frames; persistent non-TAP publishes (0,0) to allow local Time.')
    # Record when the M4 actually requested the final, filtered FS3 ON,
    # and when its new count first reached the stock SPI TX callback.
    # These timestamps share the stock timer epoch, giving an actual
    # on-device LED-command-to-first-TX bound (not a SHARC/audio latency).
    replace('    ldr r7, =TIME_US\n    blx r7                           @ exact stock tap microsecond clock',
            '    ldr r7, =TIME_US\n    blx r7                           @ exact stock tap microsecond clock\n    mov r8, r0                       @ native M4 timestamp of LED ON')
    replace('mp_led_confirmed_on:\n    adr.w r4, mp_active',
            'mp_led_confirmed_on:\n    adr.w r4, mp_active')
    replace('    beq mp_led_capture_done        @ bypassed Metronome remains quiet\n    adr.w r4, mp_counters',
            '    beq mp_led_capture_done        @ bypassed Metronome remains quiet\n    adr.w r6, mp_last_led_us\n    str r8, [r6]                   @ accepted LED ON timestamp, before original driver\n    adr.w r4, mp_counters')
    replace('    str r2, [r4, #8]\n    b mp_tx_done',
            '    str r2, [r4, #8]\n    adr.w r2, mp_last_sent_event\n    ldr r3, [r2]\n    cmp r3, r5\n    beq mp_tx_done\n    str r5, [r2]                   @ new event arrived at stock SPI TX stage\n    ldr r6, =TIME_US\n    blx r6                          @ native clock, only once per physical beat\n    adr.w r2, mp_last_led_us\n    ldr r3, [r2]\n    subs r0, r0, r3                @ modulo-32 timestamp difference, microseconds\n    adr.w r2, mp_last_led_to_tx_us\n    str r0, [r2]                   @ expose via read-only editor cmd 0x50\n    b mp_tx_done')
    replace('.equ REPLY_BYTES,  50', '.equ REPLY_BYTES,  86          @ MessagePack bin8 84-byte M4-only telemetry')
    replace('    cmp r6, #48\n    blo mp_copy', '    cmp r6, #84\n    blo mp_copy')
    replace('    .byte 0xc4, 48              @ MessagePack bin8 length 48\n    .space 48',
            '    .byte 0xc4, 84              @ MessagePack bin8 length 84\n    .space 84')
    DEST.write_text(s)
    return s
if __name__=='__main__':
    s=build()
    print(DEST,'sha256',hashlib.sha256(s.encode()).hexdigest())
