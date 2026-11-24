"""Exact Edit paint path, guarded view selection and pixel coordinates."""
import struct
import pytest,m4asm,patch_menu as pm
from m4emu import M4
from test_io_level_r09_direct_meter_m4 import FB,FILL
BASE=0x28e62898
STATS=0x28e626f0
A,B=0x281f35b8,0x281f3d2c
EA,EB=0x28128270,0x281282f8
OLD_A,OLD_B=0x28e554ad,0x28e55401
N1,N2=0x28070000,0x28070100
def setup():
    c,s=m4asm.assemble_module('src/m4/io_level_r12_edit_view.s')
    m=M4(c,BASE);m.s={k:BASE+v for k,v in s.items()};m.fills=[]
    m.stub(FILL,lambda mm:m.fills.append((mm.reg('r1'),mm.reg('r2'),mm.reg('r3'),*mm.stack_args(3))))
    m.u32(STATS+68,7|(12<<8))
    return m
def node(m,head,addr,view,active=1,paint=1,next=0):
    m.u32(head,addr)
    m.write(addr,struct.pack('<6I',active,paint,0,view,0,next))
def both(m):
    node(m,A,N1,EA);node(m,B,N2,EB)
@pytest.mark.parametrize('handler,view',[('edit_params',EA),('edit_top',EB)])
def test_both_views_and_exact_geometry(handler,view):
    m=setup();both(m);m.call(m.s[handler],FB,view)
    assert len(m.fills)==21
    assert m.u32(STATS+108)==m.u32(STATS+96)==m.u32(STATS+104)==1
    assert all(y==133 and h==5 and a==6 for x,y,w,h,c,a in m.fills)
    assert all(24<=x and x+w<=156 or 164<=x and x+w<=296 for x,y,w,h,c,a in m.fills)
    assert all(128<=y-h and y-1<=136 for x,y,w,h,c,a in m.fills)
    # Same colors and x geometry as the R11 renderer.
    c,s=m4asm.assemble_module('src/m4/io_level_r11_direct_meter.s')
    m.load(0x28e62324,c);m.fills.clear();m.u32(STATS+68,7|(12<<8))
    m.call(0x28e62324+s['r09_draw'],FB)
    play=m.fills.copy();m.fills.clear()
    m.call(m.s[handler],FB,view)
    assert [(x,w,h,c,a) for x,y,w,h,c,a in m.fills]==[(x,w,h,c,a) for x,y,w,h,c,a in play]
@pytest.mark.parametrize('va,vb,active,paint,callarg',[(EA,0x281299d0,1,1,EA),(0x2812a05c,EB,1,1,EA),(EA,EB,0,1,EA),(EA,EB,1,0,EA),(EA,EB,1,1,0x281294cc)])
def test_no_overlay_other_views(va,vb,active,paint,callarg):
    m=setup();node(m,A,N1,va,active,paint);node(m,B,N2,vb)
    m.call(m.s['edit_params'],FB,callarg)
    assert not m.fills and m.u32(STATS+108)==0
def test_first_active_node_and_bounded_cycle():
    m=setup();both(m)
    node(m,A,N1,0x1234,0,next=N1+0x40)
    node(m,N1+0x14,N1+0x40,EA)
    m.call(m.s['edit_params'],FB,EA);assert len(m.fills)==21
    m.fills.clear()
    node(m,A,N1,EA,0,next=N1)
    m.call(m.s['edit_params'],FB,EA);assert not m.fills
@pytest.mark.parametrize('stock,handler,view',[(OLD_A,'edit_params',EA),(OLD_B,'edit_top',EB)])
def test_chain_retains_original_callback_and_arguments(stock,handler,view):
    m=setup();both(m)
    m.stub(stock,lambda mm:mm.reg('r0',0x9876))
    stub=0x28e63000
    m.load(stub,pm.chain_cave(stub,stock&~1,[],[m.s[handler]]))
    assert m.call(stub,FB,view)==0x9876
    assert m.calls(stock)[0][:2]==(FB,view)
    assert len(m.fills)==21
