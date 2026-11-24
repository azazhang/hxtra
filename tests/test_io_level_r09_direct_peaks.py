"""Exact frozen R03C wrappers, including stock gate and Main audio code."""
import hashlib
from pathlib import Path
import random
import pytest
import sasm,ssim,visa_dis
from build_io_level_r01_native_frame_probe import FROZEN,FROZEN_SHA256

ROOT=Path(__file__).parents[1]
I0,I1,I8=0x80000,0x80100,0x80200
A,B=0xc3eb6,0xc3fb6
DM=0xe7440
TAG=0x494f4d39

@pytest.fixture(scope='module')
def code():
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest()==FROZEN_SHA256
    img=visa_dis.load(str(FROZEN))
    secs,syms=sasm.assemble((ROOT/'src/sharc/io_level_r09_direct_peaks.asm').read_text(),'r09.asm')
    hooks,_=sasm.assemble(f'.section pm 0xe4f6f\n CALL {syms["INPUT_PEAK"]:#x};\n.section pm 0xe503c\n CALL {syms["MAIN_PEAK"]:#x};','hooks')
    assert img.pm[0xe4f6f]==0x1014000e763d
    assert img.pm[0xe503c]==0x1000000e7795
    return img,secs,hooks

def setup(code,new,mode=0,mode1=0):
    img,secs,hooks=code
    s=ssim.Sim();s.strict_cbufen=True;s.pm.update(img.pm)
    if new:s.load(secs);s.load(hooks)
    s.u[ssim.U_MODE1]=mode1
    s.wr(0xe777e,mode)
    s.wr(0xc5b4f,0x81000)
    for frame in A,B:
        s.wr(frame,0xfacef00d);s.wr(frame+1,0);s.wr(frame+255,0xd00fecaf)
    return s

def invoke(s,entry,sig,ch=0,input=False):
    s.u[0x10]=I0;s.u[0x11]=I1;s.u[0x41]=I1;s.u[0x18]=I8;s.u[0x21]=1;s.u[0x31]=16
    for i,v in enumerate(list(sig)+[0]):s.wr(I1+i,ssim.f2b(v))
    if input:
        s.wr(I0,100000);s.wr(I8+2,0);s.wr(0xe7642,2-ch)
    else:s.wr(I0,ch)
    return s.call(entry,limit=5000)

def frame(s,a=A):
    w=[s.rd(a+i) for i in range(224,231)]
    x=0
    for v in w:x^=v
    assert x==0xffffffff
    return w

@pytest.mark.parametrize('position',range(16))
@pytest.mark.parametrize('sign',[-1,1])
def test_full_window_exact_audio_and_transient(code,position,sign):
    a,b=[setup(code,new) for new in (False,True)]
    for n in range(64):
        for ch in (0,1):
            sig=[.001]*16
            if n==17 and ch==0:sig[position]=sign*.75
            for s in (a,b):invoke(s,0xe5024,sig,ch)
            assert [a.rd(0x81000+i) for i in range(32)]==[b.rd(0x81000+i) for i in range(32)]
    assert frame(b)==frame(b,B)
    assert frame(b)[:6]==[TAG,1,0,ssim.f2b(.75),0,1]
    assert b.rd(DM+2)==0
    assert b.rd(DM+1)==0

def test_input_stereo_sidechain_preserved(code):
    a,b=[setup(code,new) for new in (False,True)]
    for ch in (0,1):
        sig=[.001]*16;sig[6+ch]=-.2*(ch+1)
        for s in (a,b):invoke(s,0xe4f4d,sig,ch,input=True)
        assert [a.rd(x) for x in range(0xe7639,0xe769b)]==[b.rd(x) for x in range(0xe7639,0xe769b)]
    assert b.rd(DM)==ssim.f2b(.4) and b.rd(DM+3)==2

def test_guard_oversize_and_swapped_header(code):
    s=setup(code,True)
    s.wr(A+1,223);s.wr(B,0xf00dface);s.wr(B+1,222<<16);s.wr(B+255,0xecafd00f)
    s.wr(DM+2,63)
    invoke(s,0xe5024,[.1]*16,1)
    assert s.rd(A+224)==0
    assert frame(s,B)[:6]==[TAG,1,0,ssim.f2b(.1),0,1]

def test_consecutive_windows_reset_independently(code):
    s=setup(code,True)
    for v in (.7,.001,0):
        s.wr(DM+2,63)
        invoke(s,0xe5024,[v]*16,1)
        assert frame(s)[3]==ssim.f2b(v)
    assert frame(s)[1]==3 and frame(s)[5]==1

@pytest.mark.parametrize('mode',range(4))
@pytest.mark.parametrize('mode1',[0,ssim.CBUFEN])
def test_all_output_modes_exact_state_and_audio(code,mode,mode1):
    a,b=[setup(code,new,mode,mode1) for new in (False,True)]
    for ch in (0,1):
        for s in (a,b):
            s.wr(DM+2,63)
            invoke(s,0xe5024,[.23,-.84]+[.005]*14,ch)
        # ASTAT's modeled latch is verified separately as actual flags.
        assert [x for i,x in enumerate(a.u) if i not in (ssim.U_ASTATX,ssim.U_ASTATY)]==[x for i,x in enumerate(b.u) if i not in (ssim.U_ASTATX,ssim.U_ASTATY)]
        assert a._pack_flags()==b._pack_flags()
        exclude=set(range(DM,DM+16))|set(range(A+224,A+231))|set(range(B+224,B+231))
        assert all(a.rd(k)==b.rd(k) for k in set(a.dm)|set(b.dm) if k not in exclude)
