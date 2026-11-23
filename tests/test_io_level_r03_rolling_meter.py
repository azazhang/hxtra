"""Assembled Cortex-M4 tests for R03 high-resolution rolling native meter on the M4.

All checks are offline. There is NO hardware load or persistent firmware write.
The display uses native 44-word metering event positions measured on live R01
in HW02. The port-to-physical Input/Output assignment remains an experimental
mapping, never asserted by these tests.
"""
import math,struct
import pytest
import m4asm
from m4emu import M4

BASE=0x28e70000
RX=0x28008000
FB=0x28020000
DRAW_FN=0x100017e8
REGISTER_FN=0x28e165f0
SEND_FN=0x28e15b30
REQ=0x2800a000
REDRAW_FN=0x28db8508
IDS=(2,5,3,6,4,6,1,5)
EDGE=(-90,-72,-60,-48,-36,-24,-18,-12,-6,-3)

def raw32(word):
    return (word>>16|word<<16)&0xffffffff

def mkframe(levels=(-70,-70,-120,-120,-120,-120,-81,-70),hdr=44,broken=False):
    w=[0]*256
    w[0]=0xf00dface
    w[1]=(hdr<<16)|0x4a77
    w[2]=0x00a81800
    w[3]=0x01100380
    w[4]=0x54000400
    w[5]=0xf0a400c1
    for i,(channel,db) in enumerate(zip(IDS,levels)):
        j=6+i*5
        w[j:j+5]=[0,0x00030000,0x00000002,channel<<16,
                   raw32(struct.unpack('<I',struct.pack('<f',float(db)))[0])]
    w[255]=0xecafd00f
    if broken:w[39]=0x99990000        # wrong output A id => fail closed
    return struct.pack('<256I',*w)

@pytest.fixture(scope='module')
def module():
    return m4asm.assemble_module('src/m4/io_level_r03_native_meter_rolling.s')

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

def symbol(m,s):return BASE+m.syms[s]
def paint(m):m.call(symbol(m,'io_meter_draw'),FB,0x2812a05c);return list(m.paint)
def bins(m):
    x=m.u32(symbol(m,'io_bar_state'))
    return x&255,(x>>8)&255,bool(x>>31)

def test_CortexM4_float_IEEE_unsigned_bins_match_known_edges(machine):
    m=machine
    vals=[-121,-100,-90,-89,-73,-72,-69,-61,-60,-49,-48,-37,-36,-30,-24,-19,-18,-13,-12,-7,-6,-4,-3,-2,-1,0,4]
    for v in vals:
        raw=struct.unpack('<I',struct.pack('<f',float(v)))[0]
        expected=max(0,min(132,int((90+v)*132/90))) if math.isfinite(v) else 0
        out=m.call(symbol(m,'io_level_to_bin'),raw)
        assert out==expected,(v,out,expected)
    for raw in (0x7f800000,0xff800000,0x7fc00000,0xffc00000):
        assert m.call(symbol(m,'io_level_to_bin'),raw)==0

def test_native_44word_meter_packet_updates_two_atomic_bins_once(machine):
    m=machine
    assert bins(m)==(0,0,False)
    x=mkframe(levels=(-30,-30,-120,-120,-120,-120,-12,-12))
    m.write(RX,x)
    m.call(symbol(m,'io_meter_frame'),0,RX)
    assert bins(m)==(88,114,True)
    assert m.u32(symbol(m,'io_bar_state')+4)==0
    assert len(m.calls(REDRAW_FN))==1
    assert m.u32(symbol(m,'io_diag_live')+16)==1
    assert m.u32(symbol(m,'io_diag_live')+20)==1
    m.call(symbol(m,'io_meter_frame'),0,RX)
    assert bins(m)==(88,114,True)
    assert len(m.calls(REDRAW_FN))==1
    assert m.u32(symbol(m,'io_diag_live')+16)==2 # full native packet repeats

def test_invalid_or_nonmeter_frame_never_updates_or_requests_redraw(machine):
    m=machine
    for kwargs in ({'hdr':0},{'hdr':14},{'hdr':44,'broken':True}):
        m.write(RX,mkframe(**kwargs))
        m.call(symbol(m,'io_meter_frame'),0,RX)
    assert bins(m)==(0,0,False)
    assert len(m.calls(REDRAW_FN))==0

def test_stale_packet_resets_both_bars_with_single_repaint(machine):
    m=machine
    m.write(RX,mkframe())
    m.call(symbol(m,'io_meter_frame'),0,RX)
    assert bins(m)[-1] is True
    m.u32(symbol(m,'io_bar_state')+4,4600)
    m.write(RX,mkframe(hdr=0))
    m.call(symbol(m,'io_meter_frame'),0,RX)
    assert bins(m)==(0,0,False)
    assert len(m.calls(REDRAW_FN))==2
    m.call(symbol(m,'io_meter_frame'),0,RX)
    assert len(m.calls(REDRAW_FN))==2

def test_home_paint_blits_two_bars_inside_free_row_clear_of_GR_edges(machine):
    m=machine
    assert paint(m)==[(FB,24,118,132,5,0x25282c,6),(FB,164,118,132,5,0x25282c,6)]
    m.paint.clear()
    m.write(RX,mkframe(levels=(-30,-30,-120,-120,-120,-120,-1,-1)))
    m.call(symbol(m,'io_meter_frame'),0,RX)
    rects=paint(m)
    assert rects[:2]==[(FB,24,118,132,5,0x25282c,6),(FB,164,118,132,5,0x25282c,6)]
    assert len(rects)==4
    assert rects[2]==(FB,24,118,88,5,0x35c878,6)
    assert rects[3]==(FB,164,118,130,5,0xf4a53a,6)
    assert all(20<=x and x+w<=300 and y-h>=112 and y<=118 for _,x,y,w,h,_,_ in rects)

def test_rollup_native_meter_values_include_all_eight_real_records(machine):
    m=machine
    vals=(-69.5,-68.9,-120,-120,-120,-120,-81.5,-69.6)
    m.write(RX,mkframe(levels=vals))
    m.call(symbol(m,'io_meter_frame'),0,RX)
    a=symbol(m,'io_diag_live')
    assert [m.u32(a+4*i) for i in (1,2,3,4,5)]==[1,1,1,1,1]
    assert [m.u32(a+32+4*i) for i in range(8)]==[struct.unpack('<I',struct.pack('<f',v))[0]>>16|((struct.unpack('<I',struct.pack('<f',v))[0]<<16)&0xffffffff) for v in vals]
    assert bins(m)==(30,29,True)

def test_readonly_editor_0x13_registers_and_returns_64B_rolling_snapshot(machine):
    m=machine
    m.call(symbol(m,'io_diag_register'))
    assert len(m.registration)==1
    cmd,(fn,check,extra)=m.registration[0]
    assert cmd==0x13 and fn==(symbol(m,'io_diag_command')|1)
    assert check==0x28e19205 and extra==0
    m.write(RX,mkframe(levels=(-30,-30,-120,-120,-120,-120,-18,-12)))
    m.call(symbol(m,'io_meter_frame'),0,RX)
    m.write(REQ+12,struct.pack('<H',0x2244))
    m.call(symbol(m,'io_diag_command'),0x20001700,REQ)
    stream,seq,status,response=m.replies[-1]
    assert (stream,seq,status)==(0x20001700,0x2244,0)
    assert response[:3]==bytes.fromhex('c50040') and len(response)==67
    p=struct.unpack('<16I',response[3:])
    assert p[:7]==(0x334d4f49,1,1,1,1,1,m.u32(symbol(m,'io_bar_state')))
    assert p[8:] == tuple(m.u32(symbol(m,'io_diag_live')+32+i*4) for i in range(8))
    assert m.u32(symbol(m,'io_bar_state'))==(0x80000000|(88)|(114<<8))

def test_db_resolution_changes_one_or_two_pixels_across_one_decibel(machine):
    m=machine
    for x,y in [(-70.05,-68.96),(-40.1,-39.0),(-19.1,-18.0)]:
        f=lambda v:struct.unpack('<I',struct.pack('<f',v))[0]
        width0=m.call(symbol(m,'io_level_to_bin'),f(x))
        width1=m.call(symbol(m,'io_level_to_bin'),f(y))
        assert 1<=width1-width0<=3,(x,y,width0,width1)

def test_real_HW02_native_packet_shape_has_exact_expected_member_id_order():
    x=mkframe(levels=(-70,-70,-120,-120,-120,-120,-81,-70))
    w=struct.unpack('<256I',x)
    assert w[1]>>16==44
    for i,channel in enumerate(IDS):
        j=6+5*i
        assert (w[j],w[j+1],w[j+2],w[j+3])==(0,0x00030000,2,channel<<16)
    assert w[0]==0xf00dface and w[255]==0xecafd00f
