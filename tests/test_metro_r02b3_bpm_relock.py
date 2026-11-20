"""METRO-TAPSYNC-R02B3-BPM-RELOCK-DSPMETER regressions.

Reproduces R02B2's premature local fallback after a fast BPM knob change,
with no corresponding LED event, and verifies relock to an accented downbeat.
The simulated click code is the actual compiled SHARC assembly selected by
HX_METRO_SPI_PHASE=1.
"""
import pytest
from test_metro_r02b3_audio_phase import click_phase,spi_event,I0


def test_fast_bpm_knob_change_does_not_create_a_click_without_tap(monkeypatch):
    c=click_phase(monkeypatch,time=.5,accent=4)
    spi_event(c,100,0);c.call()
    spi_event(c,101,0);c.call()
    assert c.sim.rd(I0+21)==1 and c.sim.rd(I0+31)==1
    c.run(16800)  # 350 ms since last 500 ms TAP pulse
    c.knobs(time=.1) # new Time 100 ms without a new TAP pulse
    c.call()
    assert c.sim.rd(I0+21)==1, 'R02B2 produces phantom beat on BPM acceleration'
    assert c.sim.rd(I0+31)==1, 'R02B2 drops external phase master prematurely'
    spi_event(c,102,0);c.call()
    assert c.sim.rd(I0+21)==2, 'Accent must continue from actual TAP events only'


def test_corrupt_spi_frame_during_tempo_edit_cannot_trigger_local_offbeat(monkeypatch):
    c=click_phase(monkeypatch,time=.5,accent=4)
    spi_event(c,50,3);c.call()
    spi_event(c,51,3);c.call()
    c.run(16800)
    c.knobs(time=.1)
    spi_event(c,51,3,good=False)
    c.call()
    assert c.sim.rd(I0+21)==1
    assert c.sim.rd(I0+31)==1
    spi_event(c,52,3)
    c.call()
    assert c.sim.rd(I0+21)==2


def test_real_tap_dropout_reacquires_accented_downbeat(monkeypatch):
    c=click_phase(monkeypatch,time=.1,accent=4)
    spi_event(c,10,0);c.call()
    spi_event(c,11,0);c.call()
    assert c.sim.rd(I0+21)==1
    c.run(2*4800+64)
    assert c.sim.rd(I0+31)==0, 'Long actual dropout must permit local fallback'
    spi_event(c,12,0);c.call()
    assert c.sim.rd(I0+31)==1
    assert c.sim.rd(I0+21)==1, 'First TAP after fallback must be accented, not arbitrary beat position'


def test_repeated_fast_slow_bpm_knob_changes_do_not_advance_accent_between_led_events(monkeypatch):
    c=click_phase(monkeypatch,time=.5,accent=4)
    spi_event(c,100,0);c.call()
    spi_event(c,101,0);c.call()
    assert c.sim.rd(I0+21)==1
    # Six knob edits without a new LED edge. In R02B2 a 0.35-second
    # hold followed by a .1s tempo created a spurious tick and beat slip.
    c.run(16800)
    for tempo in (.1,.25,.12,.35,.1,.18):
        c.knobs(time=tempo)
        c.call()
        assert c.sim.rd(I0+21)==1, ('phantom click',tempo)
        assert c.sim.rd(I0+31)==1, ('external master lost',tempo)
    # Four genuine LED edges should now complete exactly one accent bar.
    for beat in (102,103,104,105):
        spi_event(c,beat,0)
        c.call()
    assert c.sim.rd(I0+21)==1
    assert c.sim.rd(I0+31)==1


def test_timeout_suppression_is_anchored_to_last_real_tap_period(monkeypatch):
    c=click_phase(monkeypatch,time=.25,accent=4)
    spi_event(c,20,0);c.call()
    spi_event(c,21,0);c.call()
    assert c.sim.rd(I0+33)==12000  # 48 kHz x 0.25 sec
    c.run(14400) # 300ms since last real 250ms beat
    c.knobs(time=.1)
    # Under the new 100ms period, 300ms would be 3 new beats. Yet no new
    # TAP arrived, and the 250ms old tempo may still govern the next edge.
    c.call()
    assert c.sim.rd(I0+21)==1
    assert c.sim.rd(I0+31)==1
    assert c.sim.rd(I0+33)==12000
    spi_event(c,22,0);c.call()
    assert c.sim.rd(I0+33)==4800  # hold interval updates on the real TAP
