"""METRO-TAPSYNC-R02B1E-EVENT-ECHO: actual M4 binary -> simulated SPI -> SHARC binary -> M4 binary -> host."""
import struct
import pytest
import test_gr as gr
import test_metro_r02b1e_spi_canary as mt
import metro_tapsync_r02b1e_probe as probe
from unicorn.arm_const import UC_ARM_REG_R1,UC_ARM_REG_R2


def transfer(m,sim,sym,txptr,rxptr,expected_beat,expected_enable):
    # M4 executes its real Thumb TX hook on a real 256-word frame.
    mt.frame(m.u,base=txptr)
    m.call('mp_tx_stamp',{UC_ARM_REG_R1:txptr})
    marker,tap,enable,check=struct.unpack('<4I',m.u.mem_read(txptr+960,16))
    assert (marker,tap,enable)==(probe.CANARY,expected_beat,expected_enable)
    assert check==((~(marker^tap^enable))&0xffffffff)

    # The hardware-proven M4 TX word240 mapping starts at SHARC DM 0xC3DA6.
    for i,x in enumerate((marker,tap,enable,check)):
        sim.wr(0xc3da6+i,x)
    gr.block(sim,sym,'ENTRY_271A',0x96000,0.25)
    returned=[sim.rd(gr.FRAME+220+i) for i in range(4)]
    assert returned==[marker,tap,enable,check]

    # M4 runs its real Thumb return-frame hook on the output of the SHARC.
    mt.frame(m.u,base=rxptr)
    m.u.mem_write(rxptr+800,struct.pack('<I',0xF00D600D))
    m.u.mem_write(rxptr+880,struct.pack('<4I',*returned))
    m.call('mp_rx_probe',{UC_ARM_REG_R1:rxptr})
    out=probe.decode(struct.pack('<12I',*m.counters()))
    assert out['dsp_echo_integrity_valid']
    assert (out['dsp_echo_tap_count'],out['dsp_echo_enable_count'])==(tap,enable)
    assert out['tap_count_difference_m4_minus_dsp']==0
    assert out['enable_count_difference_m4_minus_dsp']==0
    return out


def test_live_m4_instructions_sharc_assembly_and_usb_parser_preserve_two_dynamic_event_changes(monkeypatch):
    with __import__("tempfile").TemporaryDirectory() as d:
        import os,m4asm,usb_commands
        open(os.path.join(d,"usb.inc"),"w").write(usb_commands.inc("metronome_phase"))
        asm=m4asm.assemble_module("src/m4/metronome_phase.s",include=(d,))
    monkeypatch.setenv('HX_METRO_EVENT_ECHO','1')
    monkeypatch.delenv('HX_METRO_SPI_CANARY',raising=False)
    m=mt.Machine(asm)
    sim,sym=gr.probe(span=256)
    gr.knobs(sim,sym,'CTRL_271A',0x96000,0,0,3)
    for _ in range(12):m.call('mp_beat')
    m.call('mp_bypass',{UC_ARM_REG_R1:8,UC_ARM_REG_R2:0})
    first=transfer(m,sim,sym,0x20002000,0x20005000,12,1)
    assert first['dsp_echo_valid_frames']==1 and first['dsp_echo_bad_checksum_frames']==0
    for _ in range(3):m.call('mp_beat')
    m.call('mp_bypass',{UC_ARM_REG_R1:8,UC_ARM_REG_R2:0})
    second=transfer(m,sim,sym,0x20002000,0x20005000,15,2)
    assert second['dsp_echo_valid_frames']==2 and second['dsp_echo_bad_checksum_frames']==0
