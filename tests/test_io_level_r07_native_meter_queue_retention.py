"""Use the exact R03C stock meter and real shared enqueue routine in SHARC sim.

No mocked success function: the fixture seeds the actual ring queue pointer
variables, and the stock assembly determines full/success itself.
"""
from pathlib import Path
import random
import pytest
import sasm,ssim,visa_dis
from build_io_level_r01_native_frame_probe import FROZEN,FROZEN_SHA256
import hashlib

ROOT=Path(__file__).parents[1]
ENTRY=0x8da6a
PATCH=0x8da7e
I0,I1,I8,OBJ=0x80000,0x80100,0x80200,0x80300
CAP,USED,TAIL,DATA=0x80400,0x80401,0x80402,0x80500

@pytest.fixture(scope='module')
def code():
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest()==FROZEN_SHA256
    img=visa_dis.load(str(FROZEN))
    s,_=sasm.assemble((ROOT/'src/sharc/native_meter_retain_on_queue_full.asm').read_text(),'retain.asm')
    assert len(s)==1 and s[0].addr==PATCH and len(s[0].words)==7
    stock={a:img.pm[a] for a in list(range(0x8cbb8,0x8cbf5))+list(range(ENTRY,0x8da85))}
    patched=stock | {PATCH+i:w for i,w in enumerate(s[0].words)}
    assert [stock[a] for a in range(PATCH,PATCH+7)]==[0xb10100000002,0x06be0408cbb8,0x0f0100000001,0x603e08042333,0x0a3e05000000,0x013e00042000,0xb10000000000]
    return stock,patched

def setup(pm,period=1,count=0,capacity=8,used=0,peak=0.0,tail=0,mode1=0):
    s=ssim.Sim();s.strict_cbufen=True;s.pm.update(pm)
    s.u[0x10]=I0;s.u[0x11]=I1;s.u[0x41]=I1;s.u[0x18]=I8;s.u[0x21]=1;s.u[0x31]=16;s.u[ssim.U_MODE1]=mode1
    s.wr(I0,period);s.wr(I0+1,OBJ);s.wr(I8,ssim.f2b(peak));s.wr(I8+1,ssim.f2b(peak));s.wr(I8+2,count)
    for a,b in [(0x9d5fc,CAP),(0x9d5fa,USED),(0x9d5f9,TAIL),(0x9d5f8,DATA),(CAP,capacity),(USED,used),(TAIL,tail),(0xc5b54,0)]:s.wr(a,b)
    return s

def block(s,signal):
    for i,v in enumerate(list(signal)+[0]):s.wr(I1+i,ssim.f2b(v))
    s.u[0x11]=I1
    return s.call(ENTRY,limit=400)

def equivalent(a,b,ignore=()):
    assert a.u==b.u
    assert a._pack_flags()==b._pack_flags()
    assert {k:v for k,v in a.dm.items() if k not in ignore}=={k:v for k,v in b.dm.items() if k not in ignore}

@pytest.mark.parametrize('mode1',[0,0x1000])
@pytest.mark.parametrize('used',[0,3,7,8])
@pytest.mark.parametrize('period,count',[(1,0),(3,0),(3,1),(3,2),(300,299)])
def test_stock_success_or_nonpublication_is_exact_and_rejection_only_preserves_peak(code,mode1,used,period,count):
    a,b=(setup(x,period=period,count=count,used=used,peak=.5,tail=5,mode1=mode1) for x in code)
    signal=[.02]*16;signal[11]=-.8
    na,nb=block(a,signal),block(b,signal)
    assert na==nb
    failure=(used==8 and count+1>=period)
    if failure:
        assert a.rd(I8)==0
        assert b.rd(I8)==ssim.f2b(.8)
    equivalent(a,b,(I8,) if failure else ())

def test_rejected_peak_reappears_at_next_successful_normal_report(code):
    old,new=(setup(x,period=3,used=8) for x in code)
    for i in range(3):
        block(old,[.8 if i==1 and j==6 else .001 for j in range(16)])
        block(new,[.8 if i==1 and j==6 else .001 for j in range(16)])
    assert old.rd(I8)==0 and new.rd(I8)==ssim.f2b(.8)
    old.wr(USED,0);new.wr(USED,0)
    for _ in range(3):
        block(old,[.001]*16);block(new,[.001]*16)
    assert old.rd(DATA+3)==ssim.f2b(.001)
    assert new.rd(DATA+3)==ssim.f2b(.8)
    assert old.rd(I8)==new.rd(I8)==0
    assert old.rd(USED)==new.rd(USED)==1

def test_repeated_full_reports_preserve_max_and_next_success_clears(code):
    s=setup(code[1],period=1,used=8)
    for v in (.3,.01,.9,.2,.05):block(s,[-v]+[0.0]*15)
    assert s.rd(I8)==ssim.f2b(.9) and s.rd(USED)==8
    s.wr(USED,7);block(s,[0.0]*16)
    assert s.rd(DATA+3)==ssim.f2b(.9) and s.rd(I8)==0
    assert s.rd(USED)==8

def test_random_normal_success_paths_bit_equal_with_same_cost(code):
    rng=random.Random(771925)
    for _ in range(60):
        period=rng.randint(1,400);count=rng.randint(0,period-1)
        used=rng.randint(0,6);peak=rng.random();tail=rng.randrange(8)
        a,b=(setup(x,period=period,count=count,used=used,peak=peak,tail=tail) for x in code)
        sig=[rng.uniform(-1,1) for _ in range(16)]
        assert block(a,sig)==block(b,sig)
        equivalent(a,b)


@pytest.mark.parametrize('mode1',[0,ssim.CBUFEN])
@pytest.mark.parametrize('position',range(16))
@pytest.mark.parametrize('sign',[-1,1])
def test_exact_original_and_patched_capture_transient_at_every_sample_position(code,mode1,position,sign):
    for program in code:
        s=setup(program,mode1=mode1)
        signal=[.001]*16;signal[position]=sign*.8
        block(s,signal)
        assert s.rd(DATA+3)==ssim.f2b(.8)
