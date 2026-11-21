#!/usr/bin/env python3
"""Generate R03C exactly-sized SHARC kernel from verified R03B source.

Fixes a verified bug: receiving old but complement-consistent SPI frames
after newer frames triggers multiple clicks at stationary BPM. Compare
31-bit event sequence in forward order by shifting the 32bit difference
left once (removing epoch bit31) and requiring positive signed delta.

Recover two original instructions using power-of-two factored gain
polynomial. All four float coefficients are divided by 2^17 and the
SCALB exponent is increased by 17; this is bit-exact for supported
Level values (verified with actual ssim oscillator/preset DSP outputs).
No additional LDR descriptors or SHARC boot-record-size changes.
"""
from pathlib import Path
import subprocess,hashlib
ROOT=Path(__file__).resolve().parents[1]
SRC_REV='5894378'
SRC='src/sharc/click_led_r03b_inplace.asm'
DEST=ROOT/'src/sharc/click_led_r03c_inplace.asm'
NAME='METRO-LEDSYNC-R03C-ORDERED-LED-MASTER'
def build():
    source=subprocess.check_output(['git','show',f'{SRC_REV}:{SRC}'],cwd=ROOT,text=True)
    s=source
    def replace(a,b):
        nonlocal s
        assert s.count(a)==1,(a,s.count(a))
        s=s.replace(a,b)
    replace('// M4 sender source: src/m4/metronome_led_r03b.s',
            '// M4 sender source: src/m4/metronome_led_r03c.s')
    replace('// METRO-LEDSYNC-R03B-INPLACE: 2-word checked M4 LED event receiver.',
            '// METRO-LEDSYNC-R03C-INPLACE: checked AND monotone 31bit LED events.')
    replace('// Valid pair is full u32 counter plus its bitwise NOT in SPI RX words 240/241.',
            '// Reject stale complete pairs, duplicate count and invalid complement; keep donor ABI.')
    replace('    F6 = 0.0781633;','    F6 = '+repr(.0781633/131072)+';')
    replace('    F9 = 0.2261586;','    F9 = '+repr(.2261586/131072)+';')
    replace('    F9 = 0.6951786;','    F9 = '+repr(.6951786/131072)+';')
    replace('    F9 = 1.0;\n    F6 = F6 + F9;',
            '    F9 = 0.00000762939453125;\n    F6 = F6 + F9;')
    replace('    R9 = 17;                            // -16, and -1 for the 0.5\n    R10 = R10 - R9;\n',
            '    // Gain polynomial factored by exact power-of-two 2^-17; SCALB uses R10.\n')
    old='''    R9 = DM(C_LED_LAST, I0);
    R11 = R8 XOR R9;
    IF EQ R0 = R0 - R0;               // no new physical LED ON
    IF NE R0 = PASS R12;              // new LED ON at next audio block
    DM(C_LED_LAST, I0) = R8;
    BTST R11 BY 31;
    IF NOT SZ R13 = R13 - R13;        // re-engage triggers accented downbeat
    JUMP c_led_next;
c_led_invalid:
'''
    new='''    R9 = DM(C_LED_LAST, I0);
    R11 = R8 XOR R9;                 // retain epoch change for downbeat
    R10 = R8 - R9;
    R10 = LSHIFT R10 BY 1;           // discard bit31 epoch; signed count delta*2
    IF LE R0 = R0 - R0;             // duplicate or replayed old frame: silent
    IF GT R0 = PASS R12, DM(C_LED_LAST, I0) = R8; // fresh beat and commit
    IF LE R11 = R11 - R11;         // stale epoch MUST NOT reset accent
    BTST R11 BY 31;
    IF NOT SZ R13 = R13 - R13;       // fresh epoch: downbeat only
    JUMP c_led_next;
c_led_invalid:
'''
    replace(old,new)
    # We used 2 new SHARC instructions in the event check and saved two
    # in the gain path; original 142 instruction total including final NOP.
    assert s.endswith('    NOP;  // unreachable record-size padding after final RTS\n')
    DEST.write_text(s)
    return s
if __name__=='__main__':
    s=build()
    print(DEST,hashlib.sha256(s.encode()).hexdigest())
