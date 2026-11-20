"""METRO-TAPSYNC-R02B2-AUDIO-PHASE: actual SHARC kernel, independent DSP simulation.

The test drives the R02B1E-verified SPI DMA words directly into SHARC memory,
and tests the real metronome assembly after every audio callback, including
phase, accent, re-entry, missing events and corrupted SPI frames.
"""
import os
import pytest
import test_click
import patch_click
import sasm
import ssim

SPI_RING=0xC3DA6
SPI_MAGIC=0x4D543242
I0=test_click.I0


def click_phase(monkeypatch,time=0.1,accent=4):
    monkeypatch.setenv('HX_METRO_SPI_PHASE','1')
    monkeypatch.delenv('HX_METRO_PHASE',raising=False)
    src=patch_click.click_source(for_size=True).replace('KIT_PM_BASE','0xe5000')
    secs,syms=sasm.assemble(src,'click_spi_phase.asm')
    c=test_click.Click(time=time,accent=accent)
    c.sim=ssim.Sim()
    c.sim.strict_cbufen=True
    c.sim.load(secs)
    c.syms=syms
    c.knobs(time=time,accent=accent,db=0.0,thru=1)
    return c


def spi_event(c,tap,enable,marker=SPI_MAGIC,good=True):
    check=(~(marker^tap^enable))&0xffffffff
    if not good:check^=0x100
    for i,v in enumerate((marker,tap,enable,check)):
        c.sim.wr(SPI_RING+i,v)


def assert_quiet(out):
    assert max(abs(x) for x in out)<1e-8


def test_valid_boot_waits_for_next_tap_then_accent_first(monkeypatch):
    c=click_phase(monkeypatch)
    spi_event(c,100,20)
    assert_quiet(c.run(320))
    assert c.sim.rd(I0+28)==1  # valid SPI seen
    assert c.sim.rd(I0+31)==1  # TAP master selected
    assert c.sim.rd(I0+21)==0  # awaiting first LED ON event
    spi_event(c,101,20)
    burst=c.call()+c.run(480)
    assert c.sim.rd(I0+21)==1
    assert test_click.freq(burst)==pytest.approx(2000,rel=.03)
    assert c.sim.rd(I0+32)==0  # exactly-once event consumed


def test_same_tap_count_cannot_retrigger_or_freerun(monkeypatch):
    c=click_phase(monkeypatch)
    spi_event(c,1,1);c.call()
    spi_event(c,2,1)
    c.call()
    beat=c.sim.rd(I0+21)
    # 99% of a quarter-note interval and duplicate ISR notifications.
    c.run(4704)
    assert c.sim.rd(I0+21)==beat
    assert c.sim.rd(I0+31)==1
    spi_event(c,2,1)
    c.call()
    assert c.sim.rd(I0+21)==beat
    spi_event(c,3,1)
    c.call()
    assert c.sim.rd(I0+21)==(beat+1)%4


def test_m4_counter_pulses_drive_one_click_per_led_edge(monkeypatch):
    c=click_phase(monkeypatch,accent=4)
    spi_event(c,100,2);c.call()
    out=[]
    for t in range(101,105):
        spi_event(c,t,2)
        out.append(c.call()+c.run(480))
    freq=[test_click.freq(x) for x in out]
    assert freq==pytest.approx([2000,1000,1000,1000],rel=.03)
    assert c.sim.rd(I0+21)==0
    spi_event(c,105,2)
    burst=c.call()+c.run(480)
    assert test_click.freq(burst)==pytest.approx(2000,rel=.03)


def test_enable_edge_discards_stale_taps_and_resets_next_downbeat(monkeypatch):
    c=click_phase(monkeypatch)
    spi_event(c,20,0);c.call()
    for t in [21,22,23]:
        spi_event(c,t,0)
        c.call()
    assert c.sim.rd(I0+21)==3
    # When audio was bypassed, three TAP beats passed. On re-enable the
    # enable counter increased and the current TAP snapshot was already 26.
    spi_event(c,26,1)
    assert_quiet(c.call())
    assert c.sim.rd(I0+21)==0
    assert c.sim.rd(I0+29)==26
    assert c.sim.rd(I0+30)==1
    assert_quiet(c.run(320))
    spi_event(c,27,1)
    burst=c.call()+c.run(480)
    assert c.sim.rd(I0+21)==1
    assert test_click.freq(burst)==pytest.approx(2000,rel=.03)


def test_corrupted_frame_cannot_generate_false_edge(monkeypatch):
    c=click_phase(monkeypatch)
    spi_event(c,20,0)
    c.call()
    spi_event(c,21,0,good=False)
    assert_quiet(c.call())
    assert c.sim.rd(I0+29)==20
    assert c.sim.rd(I0+21)==0
    spi_event(c,21,0)
    burst=c.call()+c.run(480)
    assert c.sim.rd(I0+29)==21
    assert test_click.freq(burst)==pytest.approx(2000,rel=.03)


def test_missing_taps_fall_back_to_local_clock(monkeypatch):
    c=click_phase(monkeypatch)
    spi_event(c,10,1);c.call()
    spi_event(c,11,1);c.call()
    assert c.sim.rd(I0+31)==1
    # No next edge for more than two Time intervals: preserve audible fallback.
    c.run(2*4800+96)
    assert c.sim.rd(I0+31)==0
    assert c.sim.rd(I0+21)==2
    spi_event(c,12,1)
    c.call()
    assert c.sim.rd(I0+31)==1
    assert c.sim.rd(I0+21)==3


def test_standalone_no_spi_still_plays_original_first_beat(monkeypatch):
    c=click_phase(monkeypatch)
    burst=c.call()+c.run(480)
    assert test_click.freq(burst)==pytest.approx(2000,rel=.03)
    assert c.sim.rd(I0+28)==0
    assert c.sim.rd(I0+21)==1


def test_all_calibration_storage_stays_within_metronome_instance(monkeypatch):
    c=click_phase(monkeypatch)
    spi_event(c,1,1)
    c.call()
    for offset in (28,29,30,31,32):
        assert 0<=offset<100
    assert patch_click.dsp_size()[0]==0


def test_audio_onsets_track_actual_4800_sample_tap_intervals(monkeypatch):
    c=click_phase(monkeypatch,time=0.1,accent=4)
    spi_event(c,10,0)
    c.call()       # bootstrap, no click until first M4 edge
    output=[]
    for number in range(11,14):
        spi_event(c,number,0)
        output.extend(c.run(4800))
    assert test_click.onsets(output)==[0,4800,9600]
    assert c.sim.rd(I0+21)==3


def test_audio_onsets_follow_tempo_shortening_without_double_click(monkeypatch):
    c=click_phase(monkeypatch,time=0.1,accent=4)
    spi_event(c,10,0)
    c.call()
    spi_event(c,11,0)
    first=c.run(4800)  # LED quarter beat at the initial 100-ms tempo
    # At the new faster tempo the M4 LED produces its next edge sooner.
    c.knobs(time=.08)
    spi_event(c,12,0)
    second=c.run(3840)
    spi_event(c,13,0)
    third=c.run(3840)
    output=first+second+third
    # The oscillator's 6-ms decay remains just above test_click.onsets()'s
    # 1e-6 silence threshold after only 80 ms. Test the burst amplitude
    # discontinuity at each known LED edge instead.
    for start in (0,4800,8640):
        assert max(abs(x) for x in output[start:start+64])>0.02
    for start in (4800,8640):
        assert max(abs(x) for x in output[start-32:start])<0.001
    assert c.sim.rd(I0+21)==3
