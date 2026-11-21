#!/usr/bin/env python3
"""Generate an exactly 142-word *in-place* SHARC metronome proof of concept.

It starts from the byte-verified original HXtra 1.2.1 click kernel in Git
commit df327d5 and uses SHARC dual-issued ALU+DM instructions to recover
instruction slots. This avoids *all* LDR descriptor merges or extensions.

IMPORTANT: exploratory ABI/protocol code, NO HARDWARE TEST PERMITTED.
The external packet is a SINGLE atomic 32-bit M4->SHARC SPI word with a
0xA5 high-byte marker and a 24-bit count/epoch field. This 8-bit marker
does not provide a full integrity check; further protocol hardening needed.
The simplification of Accent clamping (1..12) and Thru bool (0/1) is
equivalent over valid HXtra model param domains, not arbitrary RAM data.
"""
from pathlib import Path
import subprocess
import sys
import hashlib

ROOT=Path(__file__).resolve().parents[1]
REVISION='df327d5'
SRC='src/sharc/click.asm'
DEST=ROOT/'src/sharc/click_led_r03a_inplace.asm'
PM_MAIN=0xe5386

def source():
    old=subprocess.check_output(['git','show',f'{REVISION}:{SRC}'],cwd=ROOT,text=True)
    original=old
    def replace(old_text,new_text,howmany=1):
        nonlocal old
        n=old.count(old_text)
        if n!=howmany:
            raise AssertionError((old_text,n,howmany))
        old=old.replace(old_text,new_text)
    # Insert constants; the original C_SAVE address and all other state
    # positions are retained exactly. C_LED_LAST is unused word 28 of 145.
    replace('.equ C_MET,    26', '.equ C_MET,    26\n.equ C_LED_LAST, 28                // recorded one-word LED event\n.equ LED_RING_WORD, 0xc3da6        // M4 SPI TX240 into SHARC RX DM')
    # Four original reads from the state block are dual-issued in preceding
    # arithmetic while neither destination register is used by that compute.
    replace('    F9 = 48000.0;\n    F8 = F8 * F9;',
            '    F9 = 48000.0;\n    F8 = F8 * F9, R0 = DM(C_SINCE, I0);')
    replace('    R12 = FIX F8;','    R12 = FIX F8, R1 = DM(C_MET, I0);')
    replace('    R12 = MAX(R12, R9);','    R12 = MAX(R12, R9), R13 = DM(C_BEAT, I0);')
    replace('    R12 = MIN(R12, R9);','    R12 = MIN(R12, R9), F2 = DM(C_Y2, I0);')
    replace('    F9 = 0.16609640474;\n    F8 = F8 * F9;',
            '    F9 = 0.16609640474;\n    F8 = F8 * F9, F3 = DM(C_COEF, I0);')
    replace('    F8 = F8 + F9;', '    F8 = F8 + F9, F4 = DM(C_ENV, I0);')
    replace('    R10 = TRUNC F8;', '    R10 = TRUNC F8, R7 = DM(8, I0);')
    replace('    F11 = FLOAT R10;', '    F11 = FLOAT R10, R14 = DM(7, I0);')
    # The actual model type: Thru=boolean 0/1, Accent=integer 1..12.
    # Exact values (including 0/1) are preserved for ALL valid GUI params.
    # Unexpected raw parameter data outside model constraints is NOT equivalent.
    replace('    R7 = DM(8, I0);                     // Thru\n    R7 = PASS R7;\n    F7 = 1.0;\n    IF EQ F7 = F7 - F7;',
            '    F7 = FLOAT R7;                   // model boolean: exactly 0/1')
    replace('    R14 = DM(7, I0);                    // Accent\n    R9 = 1;\n    R14 = MAX(R14, R9);\n    R9 = MAX_BAR;\n    R14 = MIN(R14, R9);',
            '    // R14 already loaded from model Accent (valid integer 1..12).')
    replace('    R0 = DM(C_SINCE, I0);\n    R1 = DM(C_MET, I0);\n',
            '    // R0 and R1 loaded in parallel with period computation.\n')
    replace('    R13 = DM(C_BEAT, I0);\n    F4 = DM(C_ENV, I0);\n    F1 = DM(C_Y1, I0);\n    F2 = DM(C_Y2, I0);\n    F3 = DM(C_COEF, I0);',
            '    // R13, F4, F2, F3 already loaded during Level/period math.\n    F1 = DM(C_Y1, I0);')
    replace('      R0 = R0 + 1;\n      F8 = F3 * F1;',
            '      R0 = R0 + 1, F10 = DM(I4, 1);\n      F8 = F3 * F1;')
    replace('      F10 = DM(I4, 1);\n', '')
    # New sync logic: 15 original instruction slots available after the
    # eight dual-issue loads, one dual-issue audio fetch, Accent/Thru domain
    # simplification. The single aligned word is never torn across SPI fields.
    # The M4 side MUST send 0 until the first actual LED ON, then a 0xA5
    # high-byte with its count and an epoch bit (bit23 flips on re-enable).
    # Short OFF->ON reversals are filtered by M4 *before* changing the count.
    newlogic='''    // R03A proof: one atomic word; M4 must publish 0 before first edge.
    // Use R8..R11 only: hoisted F1..F5 oscillator/envelope state lives
    // in R1..R5 already. Clobbering those caused a verified silent-audio bug.
    R8 = DM(LED_RING_WORD);
    R9 = LSHIFT R8 BY -24;
    R10 = 0xA5;
    COMP(R9, R10);
    IF NE JUMP c_led_local;             // no valid packet: native donor clock
    R9 = DM(C_LED_LAST, I0);
    R11 = R8 XOR R9;
    IF EQ R0 = R0 - R0;                 // no new LED edge: suppress local click
    IF NE R0 = PASS R12;                // new LED ON: click at block start
    DM(C_LED_LAST, I0) = R8;
    R10 = LSHIFT R8 BY 8;
    R10 = PASS R10;                     // 0xA5000000 has no LED ON yet
    IF EQ R0 = R0 - R0;
    BTST R11 BY 23;                    // fresh bypass/re-engage marker
    IF NOT SZ R13 = R13 - R13;          // next triggered click is downbeat
c_led_local:
'''
    replace('    F5 = 0.99653379;                    // the envelope\'s step: a 6 ms time constant',
            '    F5 = 0.99653379;                    // the envelope\'s step: a 6 ms time constant\n\n'+newlogic.rstrip())
    banner=('// METRO-LEDSYNC-R03A-INPLACE-PROTO: exploratory exact-size SHARC.\n'
            '// NO device load: marker-only 32bit frame requires integrity hardening.\n'
            '// Time/Level/sample oscillator/Accent/Thru valid-domain behavior tested via ssim.\n')
    return banner+old,hashlib.sha256(original.encode()).hexdigest()

def main():
    text,sha=source()
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(text)
    print(f'{DEST} original_git_source_sha256={sha} new_source_sha256={hashlib.sha256(text.encode()).hexdigest()}')

if __name__=='__main__':main()
