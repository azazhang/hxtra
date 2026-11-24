"""Replay actual HW08 DSP tail words; compare exact original and fixed Thumb code."""
import json,struct,functools
from pathlib import Path
import pytest,m4asm
from m4emu import M4
from test_io_level_r09_direct_meter_m4 import BASE,RX,FB,REDRAW,FILL,wire,stats,rx,tick
ROOT=Path(__file__).parents[1]
DATA=ROOT/'tests/hardware_evidence/io-level-r09-HW08-spi-tail-20261124.json'
def machine(path):
    c,s=m4asm.assemble_module(path)
    m=M4(c,BASE);m.s={k:BASE+v for k,v in s.items()};m.stub(REDRAW);m.fills=[]
    m.stub(FILL,lambda mm:m.fills.append((mm.reg('r1'),mm.reg('r2'),mm.reg('r3'),*mm.stack_args(3))))
    return m
def packet(r):
    w=[0]*256;w[:2]=r['header'];w[224:231]=r['tail'];w[255]=r['trailer']
    return struct.pack('<256I',*w)
def test_actual_HX_stomp_frames_accept_and_paint_real_peak():
    old,new=[machine(f'src/m4/io_level_r{v}_direct_meter.s') for v in ('09','10')]
    rows=json.loads(DATA.read_text())
    valid=[r for r in rows if r['valid']]
    assert len(valid)==698
    def swap(x):return ((x>>16)|(x<<16))&0xffffffff
    assert all(swap(r['tail'][4])==384 for r in valid)
    # Replay every captured tail through both exact machine-code receivers.
    # Host polling is sparse: this does not simulate full-speed SPI coverage.
    expected=0;prev=0;hot=0
    for r in rows:
        for m in (old,new):rx(m,packet(r))
        if r['valid']:
            seq=swap(r['tail'][1])
            if seq>prev:
                prev=seq;expected+=1;hot+=swap(r['tail'][3])>=0x3d0186e2
    a,b=stats(old),stats(new)
    assert a[7]==0 and a[23]==len(valid)
    assert b[0]==0x41524f49 and b[7]==expected and b[13]==hot>0 and b[23]==0
    assert b[11]==384
    peak=max(valid,key=lambda r:swap(r['tail'][3]))
    # Actual peak payload at a fresh sequence, retained until a real UI tick.
    m=machine('src/m4/io_level_r10_direct_meter.s')
    rx(m,packet(peak));tick(m,99)
    assert stats(m)[17]>>8>=7 and stats(m)[17]&255==0
    m.call(m.s['r09_draw'],FB)
    assert len(m.fills)>2
    assert all(x>=164 for x,y,w,h,c,a in m.fills[2:])
@pytest.mark.parametrize('calls',[0,128,256,257,384,512,1024,0xffffffff])
def test_input_count_is_metadata(calls):
    m=machine('src/m4/io_level_r10_direct_meter.s')
    rx(m,wire(1,.01,.1,1,calls=calls))
    assert stats(m)[7]==1 and stats(m)[11]==calls
    rx(m,wire(2,.01,.9,2,calls=calls,bad=True))
    assert stats(m)[7]==1 and stats(m)[4]==1
def test_exact_assembled_delta():
    a,sa=m4asm.assemble_module('src/m4/io_level_r09_direct_meter.s')
    b,sb=m4asm.assemble_module('src/m4/io_level_r10_direct_meter.s')
    assert sa==sb and len(a)==len(b)
    assert a[174:180].hex()=='b9f5807f40d8' and b[174:180].hex()=='aff3008000bf'
    assert all(x==y for i,(x,y) in enumerate(zip(a,b)) if i not in set(range(174,180))|{sa['r09_stats']+3})
