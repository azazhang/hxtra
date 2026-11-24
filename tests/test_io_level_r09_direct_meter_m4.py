"""Execute actual M4 direct-peak parser and paint code with real frame shape."""
import struct
import pytest
import m4asm
from m4emu import M4
from unicorn import UC_HOOK_MEM_WRITE
BASE=0x28e90000
RX=0x28010000
FB=0x28020000
TAG=0x494f4d39
REDRAW=0x28db8509
FILL=0x100017e9
def f(v):return struct.unpack('<I',struct.pack('<f',v))[0]
def swap(v):return ((v>>16)|(v<<16))&0xffffffff
@pytest.fixture
def m():
    c,s=m4asm.assemble_module('src/m4/io_level_r09_direct_meter.s')
    m=M4(c,BASE);m.s={k:BASE+v for k,v in s.items()}
    m.stub(REDRAW);m.fills=[]
    m.stub(FILL,lambda mm:m.fills.append((mm.reg('r1'),mm.reg('r2'),mm.reg('r3'),*mm.stack_args(3))))
    return m
def stats(m):return struct.unpack('<32I',m.read(m.s['r09_stats'],128))
def wire(seq,inp,out,hot=0,calls=128,swapped=True,payload=0,bad=False):
    words=[0]*256;words[0]=0xf00dface;words[1]=payload<<16;words[255]=0xecafd00f
    w=[TAG,seq,f(inp),f(out),calls,hot];x=0xffffffff
    for v in w:x^=v
    w.append(x^int(bad));words[224:231]=[swap(v) if swapped else v for v in w]
    return struct.pack('<256I',*words)
def rx(m,packet=None):
    if packet is not None:m.write(RX,packet)
    m.call(m.s['r09_frame'],0,RX)
def tick(m,n=100):
    for _ in range(n):rx(m)
@pytest.mark.parametrize('swapped',[False,True])
def test_valid_new_packet_sequence_peak_hold_and_duplicates(m,swapped):
    rx(m,wire(1,.001,.8,1,swapped=swapped))
    rx(m,wire(2,.01,.00001,1,swapped=swapped))
    tick(m,98)
    s=stats(m)
    assert s[6:14]==(2,2,0,f(.01),f(.00001),128,1,1)
    assert s[17]==(4|(14<<8))
    assert s[5]==98 and s[20]==1
    m.call(m.s['r09_draw'],FB)
    assert len(m.fills)==20 and all(24<=x and x+w<=296 and y==118 and h==5 for x,y,w,h,c,a in m.fills)
    tick(m,300)
    assert stats(m)[17]>>8<14
    tick(m,1200)
    assert stats(m)[17]==0
def test_reject_bad_checksum_payload_and_backwards(m):
    rx(m,wire(10,.1,.2,1))
    rx(m,wire(11,.8,.9,2,bad=True))
    rx(m,wire(12,.8,.9,2,payload=223))
    rx(m,wire(9,.8,.9,2))
    rx(m,wire(13,.1,.2,2))
    s=stats(m);assert s[6:9]==(13,2,2) and s[4]==1 and s[22]==1
def test_stale_packet_cannot_fill_or_fabricate_measurement(m):
    rx(m,wire(1,.2,.9,1));tick(m,99)
    assert stats(m)[17]>0
    tick(m,1900)
    # After stale expiry a repeated valid packet must not be re-accepted.
    assert stats(m)[17]==0 and stats(m)[7]==1
def test_draw_clamps_corrupted_state(m):
    m.u32(m.s['r09_stats']+68,0xffffffff)
    m.call(m.s['r09_draw'],FB)
    assert len(m.fills)==34
    for x,y,w,h,c,a in m.fills:
        assert (24<=x and x+w<=156) or (164<=x and x+w<=296)
        assert y==118 and h==5
def test_diagnostic_read_only(m):
    reply=[]
    m.stub(0x28e165f1);m.stub(0x28e15b31,lambda mm:reply.append(mm.read(mm.reg('r3'),mm.stack_args(1)[0])))
    m.call(m.s['r09_register']);assert m.calls(0x28e165f1)[0][0]==0x1d
    req=0x28006000;m.write(req+12,struct.pack('<H',123));m.call(m.s['r09_command'],0x28005000,req)
    assert len(reply[0])==131 and reply[0][:7]==b'\xc5\x00\x80IOR9'
