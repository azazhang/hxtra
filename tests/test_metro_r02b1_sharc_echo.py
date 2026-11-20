"""METRO-TAPSYNC-R02B1-SPI-CANARY: SHARC candidate-RX probe + GR TX echo."""
import importlib
import os


def test_opt_in_sharc_probes_echo_two_candidate_dma_words(monkeypatch):
    monkeypatch.setenv('HX_METRO_SPI_CANARY','1')
    import test_gr as gr
    sim, sym = gr.probe(span=256)
    # The M4's canary would arrive in one of the candidate receive buffers.
    canary=0x4D543242
    sim.wr(0xc3da6,canary)
    sim.wr(0xc3fa6,0x4242544d)
    # Enable the normal Deluxe Comp metering path (41C holds this compressor).
    gr.knobs(sim,sym,'CTRL_271A',0x96000,0,0,3)
    gr.block(sim,sym,'ENTRY_271A',0x96000,0.25)
    assert sim.rd(gr.FRAME + 200)==0x600DF00D
    assert sim.rd(gr.FRAME + 220)==canary
    assert sim.rd(gr.FRAME + 221)==0x4242544D
    assert sim.rd(gr.FRAME+255)==0xD00FECAF


def test_default_gr_frame_probe_does_not_echo_candidate_words(monkeypatch):
    monkeypatch.delenv('HX_METRO_SPI_CANARY',raising=False)
    import test_gr as gr
    sim,sym=gr.probe(span=256)
    sim.wr(0xc3da6,0x4D543242)
    gr.knobs(sim,sym,'CTRL_271A',0x96000,0,0,3)
    gr.block(sim,sym,'ENTRY_271A',0x96000,0.25)
    assert sim.rd(gr.FRAME+220)==0
    assert sim.rd(gr.FRAME+221)==0
