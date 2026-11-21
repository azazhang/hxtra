"""R03A pure-in-place SHARC feasibility: donor 142-PM-word boot record unchanged shape.

This is an OFFLINE ONLY preflight; no HXF is loaded on hardware here.
Comparisons use the exact original kernel assembled from df327d5 (which also
byte-matches Entry2 LDR block177) versus the optimized in-place candidate.
"""
import itertools
import random
import subprocess
from pathlib import Path
import pytest
import sasm,ssim,patch_amp as pa,l6ia
import test_click
from metro_led_sharc_patch import parse_ldr

ROOT=Path(__file__).parents[1]
DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
PM_MAIN=0xe5386
LED_WORD=0xc3da6
TAG=0xA5000000

@pytest.fixture(scope='module')
def code():
    stock=subprocess.check_output(['git','show','df327d5:src/sharc/click.asm'],cwd=ROOT,text=True)
    original,_=sasm.assemble(stock.replace('KIT_PM_BASE',hex(PM_MAIN)),'installed-v121-donor-click.asm')
    test=(ROOT/'src/sharc/click_led_r03a_inplace.asm').read_text()
    new,_=sasm.assemble(test.replace('KIT_PM_BASE',hex(PM_MAIN)),'click_led_r03a_inplace.asm')
    assert len(original)==len(new)==1
    assert original[0].kind==new[0].kind=='pm'
    assert original[0].addr==new[0].addr==PM_MAIN
    assert len(original[0].words)==len(new[0].words)==142
    archive,yes=pa.load_l6ia_from_any(str(DONOR));assert yes
    entry=l6ia.parse(archive)[2]
    blocks,_,_=parse_ldr(archive[entry['payload_off']:entry['payload_off']+entry['payload_len']])
    assert list(blocks[177][3])==pa.pack_init_l48(PM_MAIN,original[0].words)
    return original,new

def kernel(secs,time=.1,db=0,accent=4,thru=1):
    c=test_click.Click(time=time,db=db,accent=accent,thru=thru)
    c.sim=ssim.Sim();c.sim.strict_cbufen=True;c.sim.load(secs)
    c.syms={'CUSTOM_AMP_ENTRY':PM_MAIN}
    c.knobs(time=time,db=db,accent=accent,thru=thru)
    return c

def compare(ca,cb,block=None):
    aa=ca.call(block)
    bb=cb.call(block)
    assert [ssim.f2b(v) for v in aa]==[ssim.f2b(v) for v in bb]
    state=(20,21,22,23,24,25,26)
    assert [ca.sim.rd(test_click.I0+i) for i in state]==[cb.sim.rd(test_click.I0+i) for i in state]
    assert ca.sim.rd(test_click.I0+28)==0
    return aa

@pytest.mark.parametrize('time,db,accent,thru',[
 (.00035,-60,1,0),(.01,-6,4,1),(.1,0,4,0),(.1001,-20,12,1),
 (.125,6,1,1),(.25,3.5,12,0),(.545,-3,4,1),(.75,-96,3,1),
 (1.,-12,6,0),(4.,-42,8,1),(8.,6,12,1),
])
def test_audio_bit_identical_for_valid_parameter_domains(code,time,db,accent,thru):
    original,modified=code
    a=kernel(original,time,db,accent,thru)
    b=kernel(modified,time,db,accent,thru)
    block=[.1*(-1 if i%3==0 else 1) for i in range(16)]
    for _ in range(24):
        compare(a,b,block)

def test_dynamic_changes_preserve_exact_donor_audio_when_no_master_packet(code):
    o,n=code
    a=kernel(o,.1,0,4,1)
    b=kernel(n,.1,0,4,1)
    rng=random.Random(19744)
    choices=[(.00035,-60,1,0),(.1,-12,4,1),(.217,6,12,1),(.545,-18,3,0),
             (.75,0,2,1),(2.,-20,5,0),(8.,3,12,1)]
    for time,db,accent,thru in choices:
        a.knobs(time=time,db=db,accent=accent,thru=thru)
        b.knobs(time=time,db=db,accent=accent,thru=thru)
        for _ in range(12):
            block=[rng.uniform(-.9,.9) for _ in range(16)]
            compare(a,b,block)

def test_zero_count_valid_master_does_not_trigger_unearned_click(code):
    _,n=code
    c=kernel(n,time=.1,accent=4)
    c.sim.wr(LED_WORD,TAG)  # packet is valid but no LED ON event yet
    for _ in range(100):
        x=c.call()
        assert not any(abs(v)>1e-7 for v in x)
    assert c.sim.rd(test_click.I0+21)==0
    assert c.sim.rd(test_click.I0+28)==TAG

def test_real_master_event_phase_edge_and_accent_from_single_atomic_word(code):
    _,n=code
    c=kernel(n,time=.1,accent=4)
    c.sim.wr(LED_WORD,TAG)
    for _ in range(8):c.call()
    c.sim.wr(LED_WORD,TAG|0x800001)
    first=c.call()+c.run(480)
    assert test_click.freq(first)==pytest.approx(2000,rel=.025)
    assert c.sim.rd(test_click.I0+21)==1
    for _ in range(400):
        c.call()
    assert c.sim.rd(test_click.I0+21)==1
    c.sim.wr(LED_WORD,TAG|0x800002)
    second=c.call()+c.run(480)
    assert test_click.freq(second)==pytest.approx(1000,rel=.025)
    assert c.sim.rd(test_click.I0+21)==2

def test_marker_invalid_resumes_local_donor_clock(code):
    _,n=code
    c=kernel(n,time=.1,accent=4)
    c.sim.wr(LED_WORD,0)
    assert test_click.onsets(c.run(3*4800+16))==[0,4800,9600,14400]
