"""R03C event-order repair: assembled SHARC regression against hardware symptoms.

R03C rejects stale but complement-consistent SPI frames and keeps
donor-identical waveform/gain under inactive external sync.
Physical double clicks and LED/audio lag are reported observations,
not proven caused by any one packet sequence without DSP/audio timestamps.
"""
from pathlib import Path
import subprocess
import pytest
import sasm,ssim
import test_click
from test_metro_led_r03b_transport import kernel,packet
from metro_led_sharc_patch import parse_ldr
import patch_amp as pa,l6ia

ROOT=Path(__file__).parents[1]
PM_MAIN=0xe5386

@pytest.fixture(scope='module')
def code():
    candidate,_=sasm.assemble((ROOT/'src/sharc/click_led_r03c_inplace.asm').read_text().replace('KIT_PM_BASE',hex(PM_MAIN)),'r03c.asm')
    donor_source=subprocess.check_output(['git','show','df327d5:src/sharc/click.asm'],cwd=ROOT,text=True)
    donor,_=sasm.assemble(donor_source.replace('KIT_PM_BASE',hex(PM_MAIN)),'donor.asm')
    old,_=sasm.assemble((ROOT/'src/sharc/click_led_r03b_inplace.asm').read_text().replace('KIT_PM_BASE',hex(PM_MAIN)),'r03b.asm')
    assert len(candidate)==len(donor)==len(old)==1
    assert (candidate[0].kind,candidate[0].addr,len(candidate[0].words))==('pm',PM_MAIN,142)
    original,_=pa.load_l6ia_from_any(str(Path.home()/'Downloads/HXtra_v1.2.1.hxf'))
    ent=l6ia.parse(original)[2]
    blocks,_,_=parse_ldr(original[ent['payload_off']:ent['payload_off']+ent['payload_len']])
    assert list(blocks[177][3])==pa.pack_init_l48(PM_MAIN,donor[0].words)
    return candidate,donor,old

def bar(c):return c.sim.rd(test_click.I0+21)
def seen(c):return c.sim.rd(test_click.I0+28)

@pytest.mark.parametrize('time,db,accent,thru',[
 (.00035,-60,1,0),(.01,-6,4,1),(.1,0,4,0),(.1001,-20,12,1),
 (.125,6,1,1),(.25,3.5,12,0),(.545,-3,4,1),(.75,-96,3,1),
 (1.,-12,6,0),(4.,-42,8,1),(8.,6,12,1)])
def test_donor_audio_bitidentical_when_no_external_master(code,time,db,accent,thru):
    newer,donor,_=code
    a=kernel((donor,),time=time,db=db,accent=accent,thru=thru)
    b=kernel((newer,),time=time,db=db,accent=accent,thru=thru)
    packet(b,0,checksum=0)
    sample=[.1*(-1 if i%3==0 else 1) for i in range(16)]
    for _ in range(35):
        x=a.call(sample);y=b.call(sample)
        assert [ssim.f2b(v) for v in x]==[ssim.f2b(v) for v in y]
        for k in (20,21,22,23,24,25,26):
            assert a.sim.rd(test_click.I0+k)==b.sim.rd(test_click.I0+k)

def test_adversarial_old_valid_pair_cannot_retrigger_click(code):
    newer,_,old=code
    for sec,should_reject in ((newer,True),(old,False)):
        c=kernel((sec,),time=.5,accent=4)
        packet(c,0);c.call()
        packet(c,0x80000001);c.call()
        packet(c,0x80000002);c.call()
        assert bar(c)==2
        packet(c,0x80000001);c.call()
        assert (bar(c)==2) is should_reject
        assert seen(c)==(0x80000002 if should_reject else 0x80000001)
        packet(c,0x80000002);c.call()
        if should_reject:
            assert bar(c)==2
            assert seen(c)==0x80000002

def test_stale_old_epoch_cannot_reset_downbeat_or_event_counter(code):
    newer,_,old=code
    for sec,should_reject in ((newer,True),(old,False)):
        c=kernel((sec,),time=.5,accent=4)
        packet(c,0);c.call()
        packet(c,0x80000001);c.call()
        packet(c,0x80000002);c.call()
        packet(c,0x00000003);c.call()
        assert bar(c)==1 and seen(c)==3
        packet(c,0x80000002);c.call()
        assert (bar(c)==1 and seen(c)==3) is should_reject

def test_valid_epoch_switch_and_complete_packet_corruption_handling(code):
    newer,_,_=code
    c=kernel((newer,),time=.1,accent=4)
    packet(c,0);c.call()
    packet(c,0x80000001)
    first=c.call()+c.run(480)
    assert test_click.freq(first)==pytest.approx(2000,rel=.025)
    packet(c,0x80000002)
    other=c.call()+c.run(480)
    assert test_click.freq(other)==pytest.approx(1000,rel=.025)
    assert bar(c)==2
    for wrong_crc in (0,0xBAD0BAD0,0xffffffff,0x7ffffffe):
        packet(c,0x80000003,checksum=wrong_crc)
        c.call()
        assert bar(c)==2 and seen(c)==0x80000002
    packet(c,0x00000003)
    nxt=c.call()+c.run(480)
    assert test_click.freq(nxt)==pytest.approx(2000,rel=.025)
    assert bar(c)==1 and seen(c)==3

def test_monotone_counter_over_low31_large_position_and_duplicates(code):
    newer,_,_=code
    c=kernel((newer,),time=.5,accent=4)
    for word in (0,0x800f0001,0x800f0001,0x800f0000,0x800f0002):
        packet(c,word);c.call()
    assert seen(c)==0x800f0002 and bar(c)==2
    packet(c,0x000f0003);c.call()
    assert seen(c)==0x000f0003 and bar(c)==1
