"""R05 real native event key bars: assembled M4 source-isolated tests (no device access)."""
import struct,math
import pytest
import m4asm
from m4emu import M4
from test_io_level_r04_full_native_ledger import (BASE,RX,FB,DRAW_FN,REGISTER_FN,SEND_FN,REQ,REDRAW_FN,native_packet,mkframe,ledger,symbol,bins)

@pytest.fixture(scope='module')
def module():
    return m4asm.assemble_module('src/m4/io_level_r05_live_source_pairs.s')

@pytest.fixture
def machine(module):
    code,syms=module
    m=M4(code,BASE)
    m.syms=syms
    m.paint=[]
    m.registration=[]
    m.replies=[]
    m.stub(REDRAW_FN)
    def register(mm):
        m.registration.append((mm.reg('r0'),struct.unpack('<3I',mm.read(mm.reg('r1'),12))))
    def reply(mm):
        n=mm.stack_args(1)[0]
        m.replies.append((mm.reg('r0'),mm.reg('r1'),mm.reg('r2'),mm.read(mm.reg('r3'),n)))
    m.stub(REGISTER_FN,register)
    m.stub(SEND_FN,reply)
    def fill(mm):
        m.paint.append((mm.reg('r0'),mm.reg('r1'),mm.reg('r2'),mm.reg('r3'),*mm.stack_args(3)))
    m.stub(DRAW_FN,fill)
    return m

def push(m,frame):
    m.write(RX,frame)
    m.call(symbol(m,'io_meter_frame'),0,RX)

def px(db):
    return max(0,min(132,int((90+db)*132/90)))

def test_two_distinct_native_event_keys_drive_two_independent_bars(machine):
    m=machine
    assert bins(m)==(0,0,False)
    push(m,native_packet(family=0x00020002,param=3,db=-40))
    assert bins(m)==(px(-40),0,True)
    assert m.u32(symbol(m,'io_live_ages'))==1
    assert m.u32(symbol(m,'io_live_ages')+4)==1
    assert m.u32(symbol(m,'io_redraw_pending'))==1
    push(m,native_packet(family=0x0002002a,param=1,db=-12))
    assert bins(m)==(px(-40),px(-12),True)
    assert m.u32(symbol(m,'io_diag_live')+20)==2
    assert m.u32(symbol(m,'io_diag_live')+24)==m.u32(symbol(m,'io_bar_state'))
    assert len(m.calls(REDRAW_FN))==0
    assert len(ledger(m))==2


def test_metronome_output_only_cannot_raise_input_meter(machine):
    m=machine
    for v in (-69,-12,-69,-12,-69):
        push(m,native_packet(family=0x0002002a,param=1,db=v))
        assert bins(m)[0]==0
        assert bins(m)[1]==px(v)
    assert m.u32(symbol(m,'io_diag_live')+20)==5


def test_guitar_input_and_output_peak_are_independent(machine):
    m=machine
    push(m,native_packet(family=0x00020002,param=3,db=-80))
    push(m,native_packet(family=0x0002002a,param=1,db=-39))
    push(m,native_packet(family=0x00020002,param=3,db=-32))
    assert bins(m)==(px(-32),px(-39),True)
    push(m,native_packet(family=0x0002002a,param=1,db=-15))
    assert bins(m)==(px(-32),px(-15),True)
    assert m.u32(symbol(m,'io_diag_live')+20)==4


def test_full_native_44word_packet_does_not_override_selected_live_bars(machine):
    m=machine
    push(m,native_packet(family=0x00020002,param=3,db=-32))
    push(m,native_packet(family=0x0002002a,param=1,db=-15))
    prev=bins(m)
    push(m,mkframe(levels=(-70,-70,-120,-120,-120,-120,-81,-70)))
    assert bins(m)==prev
    assert m.u32(symbol(m,'io_diag_live')+16)==1
    assert m.u32(symbol(m,'io_event_seq'))==6
    assert len(ledger(m))>=8


def test_native_keys_other_than_two_candidates_do_not_move_bars(machine):
    m=machine
    for fam,param,val in ((0x0002002e,1,-1),(0x00020000,2,-30),(0x0002002a,2,-2),(0x00020002,4,-8),(0x0002002a,3,-6)):
        push(m,native_packet(family=fam,param=param,db=val))
    assert bins(m)==(0,0,False)
    assert m.u32(symbol(m,'io_redraw_pending'))==0
    assert len(ledger(m))==5


def test_repaint_is_deferred_to_at_most_one_per_100_RX_frames(machine):
    m=machine
    push(m,native_packet(family=0x0002002a,param=1,db=-12))
    first=bins(m)
    blank=mkframe(hdr=0)
    for i in range(98):
        push(m,blank)
    assert len(m.calls(REDRAW_FN))==0
    push(m,blank)
    assert len(m.calls(REDRAW_FN))==1, (m.u32(symbol(m,'io_redraw_tick')),m.u32(symbol(m,'io_redraw_pending')),m.u32(symbol(m,'io_live_ages')),m.u32(symbol(m,'io_bar_state')))
    assert m.u32(symbol(m,'io_redraw_pending'))==0
    for i in range(150):
        push(m,blank)
    assert len(m.calls(REDRAW_FN))==1
    assert bins(m)==first


def test_source_specific_stale_timeout_does_not_erase_fresh_other_source(machine):
    m=machine
    push(m,native_packet(family=0x00020002,param=3,db=-32))
    push(m,native_packet(family=0x0002002a,param=1,db=-15))
    age=symbol(m,'io_live_ages')
    m.u32(age,4599)
    m.u32(age+4,0)
    push(m,mkframe(hdr=0))
    assert bins(m)==(0,px(-15),True)
    assert m.u32(age)==4600
    assert m.u32(age+4)==1
    m.u32(age+4,4599)
    push(m,mkframe(hdr=0))
    assert bins(m)==(0,0,True)


def test_0x13_640byte_ledger_reports_new_live_packed_pixels(machine):
    m=machine
    m.call(symbol(m,'io_diag_register'))
    assert m.registration[0][0]==0x13
    push(m,native_packet(family=0x00020002,param=3,db=-34))
    push(m,native_packet(family=0x0002002a,param=1,db=-16))
    m.write(REQ+12,struct.pack('<H',0x5544))
    m.call(symbol(m,'io_diag_command'),0x20001700,REQ)
    stream,seq,status,packet=m.replies[0]
    assert (stream,seq,status)==(0x20001700,0x5544,0)
    assert len(packet)==643 and packet[:3]==bytes.fromhex('c50280')
    rows=struct.unpack('<160I',packet[3:])
    assert rows[0]==0x344d4f49
    assert rows[5]==2
    assert rows[6]==m.u32(symbol(m,'io_bar_state'))
    assert rows[16:28]==tuple(struct.unpack('<12I',m.read(symbol(m,'io_event_table'),48)))
