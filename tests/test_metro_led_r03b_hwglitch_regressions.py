"""HWGLITCH01: adversarial regressions for actual R03B metronome double-clicks.

This file intentionally shows current failures with the exact assembled
SHARC kernel. The user reported audible double clicks at stable BPM and
LED-to-click perceptible lag. These are software-reproducible *plausible
mechanisms*, not an acoustic capture of the specific physical incident.
"""
from pathlib import Path
import pytest
import test_click,ssim
from test_metro_led_r03b_transport import sharc,kernel,packet

def beat_count(c):
    return c.sim.rd(test_click.I0+21)

@pytest.mark.xfail(strict=True,reason='Confirmed R03B defect: backward but complement-consistent event count triggers duplicate click; fixed in R03C')
def test_older_consistent_spi_frame_must_not_create_ghost_click(sharc):
    """A stale yet internally consistent 32-bit counter/~counter is not fresh."""
    c=kernel(sharc,time=.5,accent=4)
    packet(c,0)
    c.call()
    packet(c,0x80000001);c.call()
    packet(c,0x80000002);c.call()
    assert beat_count(c)==2
    packet(c,0x80000001)  # old complete SPI packet reappears
    c.call()
    assert beat_count(c)==2, 'R03B wrongly clicks again on stale old full frame'
    packet(c,0x80000002)  # ordinary packet again, still no physical LED edge
    c.call()
    assert beat_count(c)==2

@pytest.mark.xfail(strict=True,reason='Confirmed R03B defect: transient noTAP mode releases free-running click clock; M4 grace suppresses this in R03C')
def test_interrupted_master_must_not_add_local_click_then_led_click(sharc):
    """Brief transport unavailability can activate free-running native beat."""
    c=kernel(sharc,time=.1,accent=4)
    packet(c,0)
    c.call()
    packet(c,0x80000001)
    c.call()
    assert beat_count(c)==1
    packet(c,0,checksum=0)  # M4 cannot report TAP visibility temporarily
    for i in range(300):
        c.call()
    assert beat_count(c)==1, 'R03B generated local click without LED edge'
    packet(c,0x80000002)
    c.call()
    assert beat_count(c)==2

def test_valid_counter_stale_after_bypass_epoch_not_accept_retrograde(sharc):
    c=kernel(sharc,time=.5,accent=4)
    packet(c,0);c.call()
    packet(c,0x80000001);c.call()
    packet(c,0x80000002);c.call()
    packet(c,0x00000003);c.call() # valid new epoch and beat3
    assert beat_count(c)==1 # bar accent reset
    packet(c,0x80000002) # older epoch with old count2, still complementary
    c.call()
    assert beat_count(c)==1
