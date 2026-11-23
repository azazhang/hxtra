"""Offline assembled-Cortex-M4 verification for IO-LEVEL-R01 native RX probe.

The physical HX Stomp is never accessed. The source we test is the code
added to the exact physically flashed R03C image. No DSP bootstream changes.
"""
import json,struct
from pathlib import Path
import pytest
import m4asm
from m4emu import M4
from io_level_r01_native_frame_probe import BIN_SIZE,CMD,RX_MAGIC,RX_TRAILER,decode
from build_io_level_r01_native_frame_probe import NAME,patch,FROZEN
import patch_amp as pa,l6ia

ROOT=Path(__file__).parents[1]
BASE=0x28e70000
RX=0x28008000
REQ=0x2800a000
REGISTER=0x28e165f0
SEND=0x28e15b30

@pytest.fixture(scope='module')
def compiled():
    return m4asm.assemble_module('src/m4/io_level_r01_native_frame_probe.s')

@pytest.fixture
def machine(compiled):
    code,labels=compiled
    m=M4(code,BASE)
    m.labels=labels
    m.sent=[]
    m.registered=[]
    def register(mm):
        cmd=mm.reg('r0')
        data=struct.unpack('<3I',mm.read(mm.reg('r1'),12))
        m.registered.append((cmd,data))
    def sent(mm):
        length=mm.stack_args(1)[0]
        data=mm.read(mm.reg('r3'),length)
        m.sent.append((mm.reg('r0'),mm.reg('r1'),mm.reg('r2'),data))
    m.stub(REGISTER,register)
    m.stub(SEND,sent)
    return m

def addr(m,s):return BASE+m.labels[s]

def make_frame(first=RX_MAGIC,last=RX_TRAILER,seed=3):
    words=[((seed+i)*0x231&0xffffffff) for i in range(256)]
    words[0]=first;words[255]=last
    return struct.pack('<256I',*words)

def test_exact_native_frame_is_captured_once_preserving_input_bytes(machine):
    m=machine
    assert m.u32(addr(m,'io_state'))==1
    for bad in (make_frame(first=0x12),make_frame(last=0x0)):
        m.write(RX,bad)
        m.call(addr(m,'io_probe_frame'),0x11111111,RX)
        assert m.u32(addr(m,'io_state'))==1
        assert m.u32(addr(m,'io_stats'))==0
    original=make_frame()
    m.write(RX,original)
    m.call(addr(m,'io_probe_frame'),0xfeedbcad,RX)
    assert m.read(RX,1024)==original
    assert m.read(addr(m,'io_capture_data'),1024)==original
    assert m.u32(addr(m,'io_state'))==2
    assert m.u32(addr(m,'io_reply_header'))==0x31524f49
    assert m.u32(addr(m,'io_stats'))==1
    m.write(RX,make_frame(seed=99))
    m.call(addr(m,'io_probe_frame'),0,RX)
    assert m.read(addr(m,'io_capture_data'),1024)==original
    assert m.u32(addr(m,'io_stats'))==1

def test_editor_register_and_bin16_response_arms_new_readonly_snapshot(machine):
    m=machine
    m.call(addr(m,'io_probe_register'))
    assert len(m.registered)==1
    command,(fn,check,extra)=m.registered[0]
    assert command==CMD==0x4f
    assert fn==addr(m,'io_probe_command')|1
    assert check==0x28e19205 and extra==0
    first=make_frame()
    m.write(RX,first)
    m.call(addr(m,'io_probe_frame'),0,RX)
    m.write(REQ+0xc,struct.pack('<H',0x1234))
    m.call(addr(m,'io_probe_command'),0x2000170,REQ)
    stream,seq,status,data=m.sent[-1]
    assert (stream,seq,status)==(0x2000170,0x1234,0)
    assert len(data)==1043
    assert data[:3]==bytes.fromhex('c50410')
    assert decode(data[3:])['words_M4_raw_halfword_swapped']==list(struct.unpack('<256I',first))
    assert m.u32(addr(m,'io_state'))==1
    frozen_reply=m.read(addr(m,'io_reply_data'),1024)
    assert frozen_reply==first
    second=make_frame(seed=53)
    m.write(RX,second)
    m.call(addr(m,'io_probe_frame'),0,RX)
    assert m.read(addr(m,'io_reply_data'),1024)==frozen_reply  # RX never mutates TX reply
    m.call(addr(m,'io_probe_command'),0x2000170,REQ)
    data=m.sent[-1][3]
    second_decoded=decode(data[3:])
    assert second_decoded['sample_seq']==2
    assert second_decoded['words_M4_raw_halfword_swapped']==list(struct.unpack('<256I',second))
    assert m.u32(addr(m,'io_state'))==1

def test_unfinished_rx_capture_cannot_tear_the_stable_usb_reply(machine):
    m=machine
    m.write(REQ+0xc,struct.pack('<H',0x65))
    # RX may be mid-copy with the state still ARMED. Command must not
    # copy the partial back buffer to its immutable front buffer.
    partial=make_frame(seed=123)
    m.write(addr(m,'io_capture_data'),partial)
    assert m.u32(addr(m,'io_state'))==1
    m.call(addr(m,'io_probe_command'),0x2000170,REQ)
    response=m.sent[-1][3]
    assert response[:3]==bytes.fromhex('c50410')
    decoded=decode(response[3:])
    assert decoded['sample_seq']==0 and not decoded['complete']
    assert m.read(addr(m,'io_reply_data'),1024)==bytes(1024)
    assert m.u32(addr(m,'io_state'))==1

def test_probe_mutates_only_M4_and_preserves_frozen_SHARC_and_all_features():
    arc,is_hxf=pa.load_l6ia_from_any(str(FROZEN))
    assert is_hxf
    updated,manifest=patch(arc)
    assert manifest['modified_archive_entries']==[0]
    assert manifest['new_SHARC_instructions']==0
    assert manifest['new_DSP_bootstream_bytes']==0
    assert manifest['original_RX_GR_hook']=='0x28e55521'
    assert manifest['original_registration_chain']=='0x28e60f24'
    assert len(l6ia.parse(updated))==15
    for i in range(1,15):
        assert pa.get_entry_swapped(arc,i)==pa.get_entry_swapped(updated,i)

def test_real_browser_plan_permits_only_user_triggered_RAM_writes():
    out=ROOT/'build/browser-ramrun'/NAME
    manifest=json.loads((out/'manifest-stage.json').read_text())
    plan=json.loads((out/'regions/plan.json').read_text())
    assert manifest['hardware_tested'] is False
    assert manifest['RAM_only'] is True
    assert manifest['overlay_sector_count']==0
    assert manifest['UI_level_bars_implemented'] is False
    assert manifest['native_meter_field_offsets_verified'] is False
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['overlay_sectors']==0
    assert plan['summary']['changed']==[]
    assert len(plan['checks'])==2
    assert plan['checks'][0][0]==0x8802
    assert plan['checks'][1][1]==1023
    assert len(plan['regions'])==9
