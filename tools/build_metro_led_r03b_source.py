#!/usr/bin/env python3
"""R03B SHARC source from physically booted R03A's exact in-place kernel.

Transport is a two-word frame from M4 SPI TX slots 240/241:
  word240: full 32-bit monotonically increasing LED event counter;
           bit31 toggles on active->bypass->engage epoch.
  word241: bitwise complement of word240.
One pair is considered valid only if all 32 bits complement. The first
valid idle pair is (0,0xffffffff) and suppresses free-running metronome.
On invalid nonzero M4 transport words, silence the audio clock to avoid
false off-grid clicks. Zero is the explicit non-TAP fallback mode and
preserves donor local timing. M4 must keep the idle valid pair (0,~0)
until the first true LED-ON event. No new PM LDR records. Simulator tests required.
"""
from pathlib import Path
import hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1]
BASE_REV='ace7026'
SRC=f'{BASE_REV}:src/sharc/click_led_r03a_inplace.asm'
DEST=ROOT/'src/sharc/click_led_r03b_inplace.asm'
def build():
    text=subprocess.check_output(['git','show',SRC],cwd=ROOT,text=True)
    def edit(a,b):
        nonlocal text
        n=text.count(a)
        if n!=1:raise AssertionError(f'exact reference missing or repeated ({n}):{a[:100]}')
        text=text.replace(a,b)
    edit('// METRO-LEDSYNC-R03A-INPLACE-PROTO: exploratory exact-size SHARC.',
         '// METRO-LEDSYNC-R03B-INPLACE: 2-word checked M4 LED event receiver.')
    edit('// NO device load: marker-only 32bit frame requires integrity hardening.',
         '// Valid pair is full u32 counter plus its bitwise NOT in SPI RX words 240/241.')
    edit('// Time/Level/sample oscillator/Accent/Thru valid-domain behavior tested via ssim.',
         '// Original R03A donor kernel exactly retained outside this focused change.')
    edit('C_LED_LAST, 28                // recorded one-word LED event',
         'C_LED_LAST, 28                // last validated 32bit event count')
    edit('LED_RING_WORD, 0xc3da6        // M4 SPI TX240 into SHARC RX DM                       // not 0 after the first call: the first beat sounds at once',
         'LED_RING_WORD, 0xc3da6        // SHARC SPI RX word240; next is bitwise complement')
    # R1/F1 alias physically: load F1 only AFTER the donor's R1=1 and
    # DM(C_MET)=R1. Fuse with R9=NOT R8 below (independent register).
    edit('    F1 = DM(C_Y1, I0);\n', '')
    # The absolute-address SPI DM word requires a dedicated read: the
    # assembler cannot dual-issue an absolute DM load with an ALU compute.
    original='''    // R03A proof: one atomic word; M4 must publish 0 before first edge.
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
    replacement='''    // Two-word full 32bit complement, M4-stamped into unused SPI slots
    // 240/241 after stock TX completed. One invalid/torn pair cannot click.
    // No R1..R5 scratch use: oscillator float state has already been hoisted.
    R8 = DM(LED_RING_WORD);
    R9 = NOT R8, F1 = DM(C_Y1, I0);
    R10 = DM(LED_RING_WORD + 1);
    COMP(R9, R10);
    IF NE JUMP c_led_invalid;
    R9 = DM(C_LED_LAST, I0);
    R11 = R8 XOR R9;
    IF EQ R0 = R0 - R0;               // no new physical LED ON
    IF NE R0 = PASS R12;              // new LED ON at next audio block
    DM(C_LED_LAST, I0) = R8;
    BTST R11 BY 31;
    IF NOT SZ R13 = R13 - R13;        // re-engage triggers accented downbeat
    JUMP c_led_next;
c_led_invalid:
    R8 = PASS R8;
    IF NE R0 = R0 - R0;              // malformed nonzero pair: silence
    // Zero is an explicit off-TAP/no-LED transport mode: donor local clock.
c_led_next:
'''
    edit(original,replacement)
    # One 48-bit NOP after the kernel's final RTS pads the verified 141-word
    # body to the original donor record's 142 words. Unreachable at runtime.
    out="// M4 sender source: src/m4/metronome_led_r03b.s\n"+text+"\n    NOP;  // unreachable record-size padding after final RTS\n"
    DEST.write_text(out)
    return out
if __name__=='__main__':
    s=build()
    print(str(DEST),hashlib.sha256(s.encode()).hexdigest())
