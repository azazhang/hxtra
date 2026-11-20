"""Simulator coverage of experimental M4->SHARC metronome TAP phase bridge.

The tests exercise the actual assembled SHARC code. They cannot establish that
M4 PARAM_SEND reaches SHARC on physical bypass; that needs hardware QA.
"""
import math
import os
import pytest
import test_click
import patch_click
import patch_metro_phase
import sasm
import ssim

EV = 0xe4000


def phase_click(monkeypatch, time=0.1, accent=4):
    monkeypatch.setenv('HX_METRO_PHASE', '1')
    src = patch_click.click_source(for_size=True).replace('KIT_PM_BASE', '0xe5000')
    secs, syms = sasm.assemble(src, 'click_phase.asm')
    c = test_click.Click(time=time, accent=accent)
    c.sim = ssim.Sim()
    c.sim.strict_cbufen = True
    c.sim.load(secs)
    c.syms = syms
    c.knobs(time=time, accent=accent, db=0.0, thru=1)
    return c


def test_tap_event_anchors_click_to_immediate_audio_block(monkeypatch):
    c = phase_click(monkeypatch)
    c.run(2240)  # inside the first 100-ms beat, no natural click due yet
    c.sim.wr(EV, 1)
    audio = c.call() + c.run(480)
    assert test_click.freq(audio) == pytest.approx(1000, rel=0.03)
    assert c.sim.rd(test_click.I0 + 21) == 2
    assert c.sim.rd(test_click.I0 + 29) == 1  # M4 tempo is now the master
    assert c.sim.rd(test_click.I0 + 30) == 0  # event consumed


def test_repeated_control_update_does_not_add_a_beat(monkeypatch):
    c = phase_click(monkeypatch)
    c.call()
    c.sim.wr(EV, 1)
    c.call()
    beat = c.sim.rd(test_click.I0 + 21)
    c.sim.wr(EV, 1)  # second gain primitive receives the same event
    c.call()
    assert c.sim.rd(test_click.I0 + 21) == beat
    c.sim.wr(EV, 2)
    c.call()
    assert c.sim.rd(test_click.I0 + 21) == (beat + 1) % 4


def test_reenable_event_forces_accent_one_regardless_of_prior_phase(monkeypatch):
    c = phase_click(monkeypatch)
    c.call()
    c.sim.wr(EV, 1)
    c.call()
    c.sim.wr(EV, 2)
    c.call()
    assert c.sim.rd(test_click.I0 + 21) == 3
    c.sim.wr(EV, 3)
    burst = c.call() + c.run(480)
    assert c.sim.rd(test_click.I0 + 21) == 1
    assert test_click.freq(burst) == pytest.approx(2000, rel=0.03)
    c.sim.wr(EV, 1)
    burst2 = c.call() + c.run(480)
    assert c.sim.rd(test_click.I0 + 21) == 2
    assert test_click.freq(burst2) == pytest.approx(1000, rel=0.03)


def test_no_double_clicks_while_regular_tap_pulses_arrive(monkeypatch):
    c = phase_click(monkeypatch)
    c.call()
    c.sim.wr(EV, 1)
    c.call()
    c.run(5000)  # > one expected beat; while M4 is master suppress local clock
    assert c.sim.rd(test_click.I0 + 21) == 2
    c.sim.wr(EV, 2)
    c.call()
    assert c.sim.rd(test_click.I0 + 21) == 3


def test_missing_tap_pulses_eventually_restore_local_clock(monkeypatch):
    c = phase_click(monkeypatch)
    c.call()
    c.sim.wr(EV, 1)
    c.call()
    c.run(9700)
    assert c.sim.rd(test_click.I0 + 29) == 0
    assert c.sim.rd(test_click.I0 + 21) == 3


def test_encoded_control_values_preserve_real_usb_trim():
    src = patch_metro_phase.asm_src(EV,0xe5000)
    src = src.replace('.equ ORIG_CTRL_80, 0x60f3e2', '.equ ORIG_CTRL_80, 0xe6000')
    src += '\n.section pm 0xe6000\nORIG_CTRL_STUB:\n    RTS;\n'
    secs, syms = sasm.assemble(src, 'metronome_phase_test.asm')
    sim = ssim.Sim()
    sim.load(secs)
    ptr = 0xb5000
    for trim in (-48.0, -6.0, 0.0, 12.0):
        for number, base in enumerate((4096, 4352, 5120, 5376), 1):
            sim.wr(ptr,ssim.f2b(base+trim))
            sim.setR(4, 1)
            sim.setR(8, ptr)
            sim.call(syms['MP_CTRL_80'],limit=300)
            assert sim.rd(EV) == number
            assert ssim.b2f(sim.rd(ptr)) == pytest.approx(trim,abs=0.002)
    sim.wr(ptr,ssim.f2b(-6.0))
    sim.setR(4, 1)
    sim.setR(8, ptr)
    sim.call(syms['MP_CTRL_80'],limit=300)
    assert sim.rd(EV) == 4
    assert ssim.b2f(sim.rd(ptr)) == -6.0
