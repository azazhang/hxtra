"""R03B genuine assembled M4->SHARC LED synchronization and corruption tests.

Neither hardware flash nor pedal interaction. M4 execution is Unicorn Cortex
M4 with original microsecond timer stub, SHARC processing is the exact 142-PM
word ssim kernel that was derived from R03A's physically booted donor layout.
"""
import json
import random
import struct
import tempfile
import subprocess
from pathlib import Path
import pytest
import sasm,ssim,m4asm,usb_commands
import test_click
from test_metro_ledtrace_r01 import TraceMachine
from metro_led_sharc_patch import parse_ldr
import patch_amp as pa,l6ia

ROOT=Path(__file__).parents[1]
M4_SOURCE='src/m4/metronome_led_r03b.s'
SHARC_SOURCE=ROOT/'src/sharc/click_led_r03b_inplace.asm'
PM_MAIN=0xe5386
RX_WORD=0xc3da6
FRAME=0x20002000
TAP_LED_VISIBLE=0x28e4daee
TRACE=ROOT/'tests/hardware_evidence/METRO-LEDSYNC-M4LEDTRACE-R01-HWKNOB01-live.jsonl'

@pytest.fixture(scope='module')
def m4():
    with tempfile.TemporaryDirectory() as d:
        Path(d,'usb.inc').write_text(usb_commands.inc('metronome_phase'))
        return m4asm.assemble_module(M4_SOURCE,include=(d,))

@pytest.fixture(scope='module')
def sharc():
    compiled,syms=sasm.assemble(SHARC_SOURCE.read_text().replace('KIT_PM_BASE',hex(PM_MAIN)),'r03b.asm')
    assert len(compiled)==1 and compiled[0].kind=='pm'
    assert (compiled[0].addr,len(compiled[0].words))==(PM_MAIN,142)
    assert compiled[0].words[-1]==0
    donor,_=pa.load_l6ia_from_any(str(Path.home()/'Downloads/HXtra_v1.2.1.hxf'))
    e=l6ia.parse(donor)[2]
    blocks,_,_=parse_ldr(donor[e['payload_off']:e['payload_off']+e['payload_len']])
    original,_=sasm.assemble(subprocess.check_output(['git','show','df327d5:src/sharc/click.asm'],cwd=ROOT,text=True).replace('KIT_PM_BASE',hex(PM_MAIN)),'installed.asm')
    assert list(blocks[177][3])==pa.pack_init_l48(PM_MAIN,original[0].words)
    return compiled,original

def kernel(sharc,time=.1,db=0,accent=4,thru=1):
    secs=sharc[0]
    c=test_click.Click(time=time,db=db,accent=accent,thru=thru)
    c.sim=ssim.Sim()
    c.sim.strict_cbufen=True
    c.sim.load(secs)
    c.syms={'CUSTOM_AMP_ENTRY':PM_MAIN}
    c.knobs(time=time,db=db,accent=accent,thru=thru)
    return c

class BMachine(TraceMachine):
    def emit(self,colour,us=None,idx=2):
        if us is not None:self.time_us=us
        return self.call('mp_led_capture',r0=idx,r1=colour)
    def prepare(self):
        self.set_tap()
        self.uc.mem_write(TAP_LED_VISIBLE,b'\x01')
        frame=bytearray(1024)
        struct.pack_into('<I',frame,0,0xFACEF00D)
        struct.pack_into('<I',frame,4,48)
        struct.pack_into('<I',frame,1020,0xD00FECAF)
        self.uc.mem_write(FRAME,bytes(frame))
    def stamp(self):
        self.call('mp_tx_stamp',r1=FRAME)
        return struct.unpack('<2I',self.uc.mem_read(FRAME+960,8))
    def ctrs(self):
        at=0x28e70000+self.sym['mp_counters']
        return struct.unpack('<12I',self.uc.mem_read(at,48))
    def bypass(self,on):
        self.call('mp_bypass',r1=8,r2=0 if on else 1)

def packet(c,word,checksum=None):
    c.sim.wr(RX_WORD,word)
    c.sim.wr(RX_WORD+1, (~word)&0xffffffff if checksum is None else checksum)

@pytest.mark.parametrize('time,db,accent,thru',[
 (.00035,-60,1,0),(.01,-6,4,1),(.1,0,4,0),(.1001,-20,12,1),
 (.125,6,1,1),(.25,3.5,12,0),(.545,-3,4,1),(.75,-96,3,1),
 (1.,-12,6,0),(4.,-42,8,1),(8.,6,12,1),
])
def test_invalid_zero_pair_preserves_exact_donor_audio(sharc,time,db,accent,thru):
    altered=kernel(sharc,time,db,accent,thru)
    base=kernel((sharc[1],),time,db,accent,thru)
    packet(altered,0,checksum=0) # R03B sender explicitly disabled
    sample=[.1*(-1 if k%3==0 else 1) for k in range(16)]
    for _ in range(20):
        a=base.call(sample);b=altered.call(sample)
        assert [ssim.f2b(x) for x in a]==[ssim.f2b(x) for x in b]
        for i in (20,21,22,23,24,25,26):
            assert base.sim.rd(test_click.I0+i)==altered.sim.rd(test_click.I0+i)

def test_idle_valid_pair_is_silent_even_over_20000_samples(sharc):
    c=kernel(sharc)
    packet(c,0)
    out=c.run(20000)
    assert max(abs(x) for x in out)<1e-7
    assert c.sim.rd(test_click.I0+21)==0

def test_full_checked_pair_triggers_accurate_accented_LED_clock(sharc):
    c=kernel(sharc,time=.1)
    packet(c,0)
    c.run(160)
    packet(c,0x80000001)
    first=c.call()+c.run(480)
    assert test_click.freq(first)==pytest.approx(2000,rel=.025)
    assert c.sim.rd(test_click.I0+21)==1
    # no event for >2 native quarter-note times: no phantom click
    residual=c.run(12000)
    assert max(abs(v) for v in residual[-4000:])<1e-7
    assert c.sim.rd(test_click.I0+21)==1
    packet(c,0x80000002)
    second=c.call()+c.run(480)
    assert test_click.freq(second)==pytest.approx(1000,rel=.025)
    assert c.sim.rd(test_click.I0+21)==2
    packet(c,0x00000003) # epoch bit toggled on bypass -> accented again
    downbeat=c.call()+c.run(480)
    assert test_click.freq(downbeat)==pytest.approx(2000,rel=.025)
    assert c.sim.rd(test_click.I0+21)==1

def test_torn_or_corrupted_event_pair_never_causes_click(sharc):
    c=kernel(sharc,time=.1)
    packet(c,0)
    c.run(80)
    packet(c,0x80000001)
    c.call()
    c.run(2400)
    base=c.sim.rd(test_click.I0+21)
    assert base==1
    for corruption in [0,0xBAD0BAD0,0xffffffff,0x7ffffffe,0x80000003]:
        packet(c,0x80000002,checksum=corruption)
        c.run(7000)
        assert c.sim.rd(test_click.I0+21)==base
        assert c.sim.rd(test_click.I0+28)==0x80000001
    packet(c,0x80000002)
    c.call()
    assert c.sim.rd(test_click.I0+21)==2
    assert c.sim.rd(test_click.I0+28)==0x80000002

def test_random_corrupted_payload_and_checksum_disallow_phantom_event(sharc):
    c=kernel(sharc,time=.1)
    packet(c,0)
    c.run(64)
    rng=random.Random(93)
    for _ in range(90):
        word=rng.getrandbits(32)
        bad=(~word ^ (1<<rng.randrange(32)))&0xffffffff
        packet(c,word,bad)
        c.call()
    assert c.sim.rd(test_click.I0+21)==0
    assert c.sim.rd(test_click.I0+28)==0

def test_m4_spi_valid_idle_then_led_events_and_short_dark_reversal(m4):
    m=BMachine(m4);m.prepare()
    assert m.stamp()==(0,0xffffffff)
    m.emit(1,us=1000000)
    assert m.ctrs()[0]==0x80000001
    assert m.stamp()==(0x80000001,0x7ffffffe)
    m.emit(0,us=1100000)
    m.emit(1,us=1101870) # 1.870ms OFF->ON, physically near invisible
    assert m.ctrs()[4]==1 and m.ctrs()[0]==0x80000001
    assert m.stamp()==(0x80000001,0x7ffffffe)
    m.emit(0,us=1300000)
    m.emit(1,us=1350000)
    assert m.stamp()==(0x80000002,0x7ffffffd)
    assert not m.alignment_errors
    assert m.ctrs()[2]>=3

def test_bypass_and_non_tap_mode_preserve_other_behavior(m4):
    m=BMachine(m4);m.prepare()
    m.emit(1,us=1000000);assert m.ctrs()[0]==0x80000001
    m.bypass(False)
    m.emit(0,us=1200000)
    m.emit(1,us=1600000)
    assert m.ctrs()[0]==0x80000001
    m.bypass(True)
    m.emit(0,us=1700000)
    m.emit(1,us=1950000)
    assert m.ctrs()[0]==2, 'epoch toggled once on re-engage'
    m.bypass(True)
    m.emit(0,us=2200000)
    m.emit(1,us=2500000)
    assert m.ctrs()[0]==3, 'redundant on cannot reset the epoch'
    m.set_tap(False)
    assert m.stamp()==(0,0)
    m.set_tap(True)
    assert m.stamp()==(3,0xfffffffc)
    m.uc.mem_write(TAP_LED_VISIBLE,b'\x00')
    assert m.stamp()==(0,0)

def test_replay_every_physical_HWKNOB01_LED_command_and_filter_short_gaps(m4):
    rows=[json.loads(x) for x in TRACE.read_text().splitlines() if x.strip()]
    events={e['sequence']:e for r in rows for e in r.get('events',[])}
    assert len(events)==620
    m=BMachine(m4);m.prepare()
    for seq in sorted(events):
        ev=events[seq]
        m.emit(1 if ev['led_lit'] else 0,us=ev['timestamp_us_u32'])
    state=m.ctrs()
    assert state[4]==6, 'the six observed <20ms OFF->ON churn events must be removed'
    assert (state[0]&0x7fffffff)==310-6
    assert (state[0]>>31)==1
    assert not m.alignment_errors

def test_real_unicorn_m4_packet_drives_real_ssim_sharc_click(sharc,m4):
    m=BMachine(m4);m.prepare()
    c=kernel(sharc,time=.5,accent=4)
    word,crc=m.stamp();packet(c,word,crc)
    assert max(abs(x) for x in c.run(32))<1e-6
    m.emit(1,us=1000000)
    word,crc=m.stamp()
    assert crc==(~word)&0xffffffff
    packet(c,word,crc)
    first=c.call()+c.run(480)
    assert test_click.freq(first)==pytest.approx(2000,rel=.025)
    m.emit(0,us=1270000)
    m.emit(1,us=1545000)
    word,crc=m.stamp();packet(c,word,crc)
    second=c.call()+c.run(480)
    assert test_click.freq(second)==pytest.approx(1000,rel=.025)

def test_spi_unrelated_frame_slots_guarded(m4):
    m=BMachine(m4);m.prepare()
    m.emit(1,us=1000000)
    struct.pack_into('<I',bytearray(),0,0) if False else None
    m.uc.mem_write(FRAME+4,struct.pack('<I',240)) # payload too long
    m.stamp()
    assert m.ctrs()[3]>=1
    assert m.ctrs()[2]==0
