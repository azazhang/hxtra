"""Exact assembled R10/R11 delta, every boundary and physical frame replay."""
import json,struct
from pathlib import Path
import pytest,m4asm
from test_io_level_r10_receiver_fix import machine,packet,DATA
from test_io_level_r09_direct_meter_m4 import stats,rx,tick,wire,FB
P='src/m4/io_level_r11_direct_meter.s'
OLD='src/m4/io_level_r10_direct_meter.s'
DB=list(range(-75,1,5))
BITS=[struct.unpack('<I',struct.pack('<f',10**(d/20)))[0] for d in DB]
def test_uniform_every_threshold():
    m=machine(P)
    b=m.s['r09_bin']
    assert m.call(b,0)==0
    for i,u in enumerate(BITS):
        assert m.call(b,u-1)==i
        assert m.call(b,u)==i+1
        assert m.call(b,u+1)==i+1
    assert m.call(b,0x40000000)==16
def test_exact_delta():
    a,sa=m4asm.assemble_module(OLD);b,sb=m4asm.assemble_module(P)
    assert sa==sb and len(a)==len(b)
    level=sa['r09_levels']
    assert struct.unpack_from('<16I',b,level)==tuple(BITS)
    matches=[i for i in range(sa['r09_draw'],sa['r09_draw_bg'],2) if a[i:i+2]==bytes.fromhex('062d')]
    assert len(matches)==1 and b[matches[0]:matches[0]+2]==bytes.fromhex('0a2d')
    assert all(x==y for i,(x,y) in enumerate(zip(a,b)) if i not in set(range(level,level+64))|{matches[0],sa['r09_stats']+3})
def test_hardware_replay_preserves_receiver_counters():
    a,b=machine(OLD),machine(P)
    for row in json.loads(DATA.read_text()):
        pkt=packet(row)
        rx(a,pkt);rx(b,pkt)
    sa,sb=stats(a),stats(b)
    assert sa[7]>0 and sa[7]==sb[7]
    assert sa[1:15]==sb[1:15]
    assert sb[0]==0x42524f49
def test_independent_channels_and_hot_paint_semantics():
    m=machine(P)
    rx(m,wire(1,10**(-45/20),10**(-30/20),1,calls=384));tick(m,99)
    assert stats(m)[17]==7|(10<<8)
    m.call(m.s['r09_draw'],FB)
    assert len(m.fills)==19 and stats(m)[26]==1
    m=machine(P)
    rx(m,wire(1,0,10**(-35/20),0,calls=384));tick(m,99)
    assert stats(m)[17]==9<<8
    m.call(m.s['r09_draw'],FB)
    assert stats(m)[26]==0
def test_real_peak_draws_eleven_or_twelve_leds():
    rows=[r for r in json.loads(DATA.read_text()) if r['valid']]
    swap=lambda x:((x>>16)|(x<<16))&0xffffffff
    peak=max(rows,key=lambda r:swap(r['tail'][3]))
    m=machine(P);rx(m,packet(peak));tick(m,99)
    assert stats(m)[17]>>8==12 # about -19.3 dBFS => -20 threshold
    # Real hardware input noise is below -75 dBFS here.
    assert stats(m)[17]&255==0
    m.call(m.s['r09_draw'],FB);assert len(m.fills)==14
