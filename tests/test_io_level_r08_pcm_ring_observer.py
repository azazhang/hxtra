"""Execute the actual M4 observer; fake producer writes the real M0 ring layout."""
import struct
import pytest
import m4asm
from m4emu import M4
from unicorn import UC_HOOK_MEM_WRITE,UC_HOOK_MEM_READ
BASE=0x28e90000
CTX=0x20006338; DESCS=0x20007a80; BUF=0x2000b3f0
@pytest.fixture
def m():
    c,s=m4asm.assemble_module('src/m4/io_level_r08_pcm_ring_observer.s');m=M4(c,BASE);m.s={k:BASE+v for k,v in s.items()};m.map(0x20000000,0x10000)
    m.u32(CTX+0x30,DESCS);m.u32(CTX+0x1c,BUF)
    for j in range(8):
        m.u32(DESCS+32*j+0x10,BUF+224*j);m.u32(DESCS+32*j+0x18,192)
    return m

def cursor(m,index,boundary,offset=4):
    m.u8(CTX+0x40,index);m.write(CTX+0x46,struct.pack('<H',offset));m.u32(CTX+0x50,(boundary+offset//4)&0xffffffff)

def fill(m,index,samples):
    data=[]
    for v in samples:
        data.extend((((int(a)<<8)&0xffffffff)|(1 if j==0 else 0)) for j,a in enumerate(v))
    m.write(BUF+224*index,struct.pack('<%dI'%len(data),*data));m.u32(DESCS+32*index+0x14,len(data)*4)

def stat(m):return struct.unpack('<32I',m.read(m.s['pcm_stats'],128))
def call(m):m.call(m.s['pcm_ring_frame'])
def sample(out=0,inp=0):return [out,-out,0,0,inp,-inp,0,0]

def test_seed_then_short_negative_peak_and_independent_input(m):
    cursor(m,0,0);call(m)
    assert stat(m)[4]==1 and stat(m)[6]==0
    a=[sample()]*6;a[5]=sample(0,100000);a[2]=sample(400000,0);fill(m,0,a);cursor(m,1,48);call(m)
    s=stat(m);assert s[5:8]==(1,6,0);assert s[13:17]==(100000,400000,100000,400000);assert s[17:21]==(1,1,1,1)
    call(m);assert stat(m)[6]==6

def test_six_descriptors_wrap_variable_lengths_and_all_samples(m):
    cursor(m,6,1000);call(m)
    lengths=[6,7,6,7,6,7];idx=[6,7,0,1,2,3]
    for j,n in zip(idx,lengths):fill(m,j,[sample(125000,0)]*n)
    cursor(m,4,1000+8*sum(lengths));call(m)
    s=stat(m);assert s[5]==1 and s[6]==sum(lengths) and s[18]==sum(lengths) and s[19]==0 and s[20]==sum(lengths);assert s[31]==sum(lengths)

def test_stale_ring_and_overrun_explicitly_counted(m):
    cursor(m,0,0);call(m);cursor(m,0,8*48);call(m)
    s=stat(m);assert s[4]==2 and s[6]==0 and s[8]==384 and s[10]==384
    fill(m,0,[sample(80000)]*6);cursor(m,1,432);call(m);assert stat(m)[6]==6

def test_bad_pointer_rejected_without_reading_unmapped_memory(m):
    cursor(m,0,0);call(m);fill(m,0,[sample(400000)]*6);m.u32(DESCS+0x10,0xffffffff);cursor(m,1,48);call(m)
    s=stat(m);assert s[6]==0 and s[7]==1 and s[21]==1

def test_bad_sync_and_boundary_mismatch_never_committed(m):
    cursor(m,0,0);call(m);fill(m,0,[sample(400000)]*6);m.u32(BUF,0);cursor(m,1,48);call(m);assert stat(m)[22]==1 and stat(m)[6]==0
    fill(m,0,[sample(400000)]*6);cursor(m,1,56);call(m);assert stat(m)[21]==1 and stat(m)[6]==0
    cursor(m,1,48);call(m);assert stat(m)[6]==6 and stat(m)[18]==6

def test_saturation_and_no_shared_SRAM_writes(m):
    cursor(m,0,0);call(m);v=[0,-8388608,0,0,-8388608,0,0,0];fill(m,0,[v]*6);cursor(m,1,48)
    writes=[];m.uc.hook_add(UC_HOOK_MEM_WRITE,lambda uc,access,address,size,value,user:writes.append(address),begin=0x20000000,end=0x2000ffff);call(m)
    assert not writes;assert stat(m)[13:17]==(8388608,8388608,8388608,8388608)

def test_producer_overtake_invalidates_batch(m):
    cursor(m,0,0);call(m)
    for j in range(6):fill(m,j,[sample(400000)]*6)
    cursor(m,6,288);fired=[]
    def race(uc,access,address,size,value,user):
        if not fired:fired.append(True);cursor(m,0,384)
    m.uc.hook_add(UC_HOOK_MEM_READ,race,begin=BUF,end=BUF+4);call(m)
    assert stat(m)[23]==1 and stat(m)[6]==0

def test_command_returns_versioned_readonly_128_byte_snapshot(m):
    reply=[]
    m.stub(0x28e165f1);m.stub(0x28e15b31,lambda mm:reply.append(mm.read(mm.reg('r3'),mm.stack_args(1)[0])))
    m.call(m.s['pcm_register']);assert m.calls(0x28e165f1)[0][0]==0x1d
    req=0x28006000;m.write(req+12,struct.pack('<H',123));m.call(m.s['pcm_command'],0x28005000,req)
    assert len(reply[0])==131 and reply[0][:7]==b'\xc5\x00\x80IOR8'
