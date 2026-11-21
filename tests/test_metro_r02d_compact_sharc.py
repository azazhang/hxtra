"""R02D: execute exact donor 142+14-instruction length-preserving SHARC kernel.

The source reproduces the exact installed HXtra 1.2.1 code except one
trampoline. The external phase source is FS3's *post-visibility* LED bus on
transition. The M4 test covers how dark->lit transitions publish counts.
"""
from pathlib import Path
import pytest
import test_click
import ssim,sasm

SOURCE=Path(__file__).parents[1]/'src/sharc/click_led_egress_compact.asm'
PM_ORIGINAL=0xe5386
PM_SHIM=0xe52c4
LED_RING=0xc3da6
LED_MARKER=0x4d543242
I0=test_click.I0


def kernel(time=.1,accent=4,db=0,thru=1):
    text=SOURCE.read_text().replace('KIT_PM_BASE',hex(PM_ORIGINAL)).replace('LED_PROBE_BASE',hex(PM_SHIM))
    secs,syms=sasm.assemble(text,'click_led_egress.asm')
    assert [(s.kind,s.addr,len(s.words)) for s in secs]==[('pm',PM_ORIGINAL,142),('pm',PM_SHIM,14)]
    c=test_click.Click(time=time,accent=accent,db=db,thru=thru)
    c.sim=ssim.Sim()
    c.sim.strict_cbufen=True
    c.sim.load(secs)
    c.syms=syms
    c.knobs(time=time,accent=accent,db=db,thru=thru)
    return c


def marker(c,count,valid=True):
    c.sim.wr(LED_RING,LED_MARKER if valid else 0)
    c.sim.wr(LED_RING+1,count)
    c.sim.wr(LED_RING+2,0)
    c.sim.wr(LED_RING+3,(~(LED_MARKER^count))&0xffffffff)


def silent(xs):
    assert max(abs(x) for x in xs)<1e-6


def test_no_physical_led_edge_must_never_generate_a_metronome_click_even_after_bpm_edits():
    c=kernel(time=.5)
    marker(c,0)
    silent(c.run(160))
    for v in (.1,.25,.08,.3,.12,.5):
        c.knobs(time=v)
        silent(c.run(320))
    assert c.sim.rd(I0+21)==0


def test_first_illuminated_fs3_led_event_accented_then_three_normal_clicks():
    c=kernel(time=.1,accent=4)
    marker(c,0)
    silent(c.run(64))
    for n,freq in [(0x80000001,2000),(0x80000002,1000),(0x80000003,1000),(0x80000004,1000),(0x80000005,2000)]:
        marker(c,n)
        burst=c.call()+c.run(480)
        assert test_click.freq(burst)==pytest.approx(freq,rel=.025)
    assert c.sim.rd(I0+21)==1


def test_multiple_bpm_knob_changes_do_not_create_offbeat_audio_and_relock_next_actual_flash():
    c=kernel(time=.5,accent=4)
    marker(c,0);silent(c.run(160))
    marker(c,0x80000001)
    first=c.call()+c.run(480)
    assert test_click.freq(first)==pytest.approx(2000,rel=.025)
    for v in (.14,.5,.08,.25,.17,.32):
        c.knobs(time=v)
        residual=c.run(640)
        # Decaying envelope from initial event has no additional re-trigger.
        assert c.sim.rd(I0+21)==1
        assert c.sim.rd(I0+28)==0x80000001
    marker(c,0x80000002)
    second=c.call()+c.run(480)
    assert test_click.freq(second)==pytest.approx(1000,rel=.025)
    assert c.sim.rd(I0+21)==2


def test_reenable_without_illuminating_led_does_not_trigger_accent():
    c=kernel(time=.1,accent=4)
    marker(c,0);c.run(64)
    marker(c,0x80000001);c.call()
    marker(c,0x80000002);c.call()
    assert c.sim.rd(I0+21)==2
    # Bypass disables publication; re-enable waits for a fresh visible LED.
    residual=c.run(8000)
    # The preceding 6-ms envelope naturally decays after the bypass event.
    # What matters is zero additional *trigger* and silence after decay.
    assert max(abs(x) for x in residual[4800:])<1e-6
    assert c.sim.rd(I0+21)==2
    marker(c,3)   # high bit toggles only when next *visible* LED is lit
    out=c.call()+c.run(480)
    assert test_click.freq(out)==pytest.approx(2000,rel=.025)
    assert c.sim.rd(I0+21)==1


def test_absent_transport_keeps_exact_donor_metronome_free_running_behavior():
    c=kernel(time=.1,accent=4)
    marker(c,0,valid=False)
    out=c.run(3*4800+16)
    assert test_click.onsets(out)==[0,4800,9600,14400]
    assert c.sim.rd(I0+21)==0


def test_zero_thru_really_mutes_input_and_level_sensitivity_is_preserved():
    c=kernel(time=.1,accent=4,db=-12,thru=0)
    marker(c,0)
    xs=c.run(160,[0.2]*16)
    silent(xs)
    marker(c,0x80000001)
    on=c.call()+c.run(480)
    assert max(abs(v) for v in on)>0.05
    assert test_click.freq(on)==pytest.approx(2000,rel=.025)
