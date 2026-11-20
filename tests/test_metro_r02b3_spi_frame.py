"""METRO-TAPSYNC-R02B3-BPM-RELOCK-DSPMETER: execute actual Thumb TX/RX hooks in Unicorn."""
import os
import struct
import tempfile
import pytest
import m4asm
import usb_commands
import metro_tapsync_r02b3_probe as probe
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
BASE=0x28e70000
STOP=0x28001000
FS=0x28d9607c

@pytest.fixture(scope='module')
def asm():
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d,'usb.inc'),'w').write(usb_commands.inc('metronome_phase'))
        return m4asm.assemble_module('src/m4/metronome_phase.s',include=(d,))

class Machine:
    def __init__(self,asm):
        code,self.sym=asm
        self.code=code
        self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        self.u.mem_map(0x28000000,0x1000000)
        self.u.mem_map(0x20000000,0x10000)
        self.u.mem_write(BASE,code)
        self.u.mem_write(STOP,b'\x00\xbf')
        self.u.reg_write(UC_ARM_REG_SP,0x2000f000)
        self.u.hook_add(UC_HOOK_CODE,self.hook)
    def hook(self,u,addr,size,_):
        if addr==STOP:u.emu_stop()
        elif addr==FS:
            u.reg_write(UC_ARM_REG_R0,42)
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR)|1)
    def call(self,name,regs={}):
        for reg,val in regs.items():self.u.reg_write(reg,val)
        self.u.reg_write(UC_ARM_REG_LR,STOP|1)
        self.u.emu_start((BASE+self.sym[name])|1,STOP,count=3000)
        assert self.u.reg_read(UC_ARM_REG_PC)==STOP
    def counters(self):
        return struct.unpack('<12I',self.u.mem_read(BASE+self.sym['mp_counters'],48))

def frame(u,base=0x20002000,payload=0):
    u.mem_write(base,bytes(1024))
    u.mem_write(base,struct.pack('<2I',0xFACEF00D,payload))
    u.mem_write(base+1020,struct.pack('<I',0xD00FECAF))
    return base

def test_tx_hook_stamps_valid_short_frames_with_atomic_canary_last(asm):
    m=Machine(asm)
    for _ in range(4):m.call('mp_beat')
    for _ in range(2):m.call('mp_bypass',{UC_ARM_REG_R1:8,UC_ARM_REG_R2:0})
    p=frame(m.u)
    m.call('mp_tx_stamp',{UC_ARM_REG_R1:p})
    assert m.counters()[:4]==(4,2,1,0)
    marker,beats,enable,check=struct.unpack('<4I',m.u.mem_read(p+960,16))
    assert(marker,beats,enable)==(probe.CANARY,4,2)
    assert check==((~(beats^enable^marker))&0xffffffff)
    assert struct.unpack('<I',m.u.mem_read(p+1020,4))[0]==0xD00FECAF

def test_tx_hook_skips_large_and_malformed_frames(asm):
    m=Machine(asm)
    p=frame(m.u,payload=231)
    m.call('mp_tx_stamp',{UC_ARM_REG_R1:p})
    assert m.counters()[2:4]==(0,1)
    assert m.u.mem_read(p+960,16)==bytes(16)
    p=frame(m.u)
    m.u.mem_write(p,struct.pack('<I',0x12345678))
    m.call('mp_tx_stamp',{UC_ARM_REG_R1:p})
    assert m.counters()[2:4]==(0,2)
    p=frame(m.u)
    m.u.mem_write(p+1020,struct.pack('<I',0x12345678))
    m.call('mp_tx_stamp',{UC_ARM_REG_R1:p})
    assert m.counters()[2:4]==(0,3)

def test_rx_hook_captures_gr_echo_without_modifying_received_frame(asm):
    m=Machine(asm)
    p=frame(m.u,base=0x20005000)
    m.u.mem_write(p+800,struct.pack('<I',0xF00D600D))
    beat,enable=12,3
    checksum=(~(probe.CANARY^beat^enable))&0xffffffff
    m.u.mem_write(p+880,struct.pack('<4I',probe.CANARY,beat,enable,checksum))
    before=bytes(m.u.mem_read(p,1024))
    m.call('mp_rx_probe',{UC_ARM_REG_R1:p})
    assert bytes(m.u.mem_read(p,1024))==before
    assert m.counters()[4:11]==(1,probe.CANARY,beat,enable,checksum,1,0)
    assert probe.decode(struct.pack('<12I',*m.counters()))['revision']=='METRO-TAPSYNC-R02B3-BPM-RELOCK-DSPMETER'

def test_rx_hook_ignores_non_gr_frames(asm):
    m=Machine(asm)
    p=frame(m.u,base=0x20005000)
    m.call('mp_rx_probe',{UC_ARM_REG_R1:p})
    assert m.counters()[4:11]==(0,0,0,0,0,0,0)

def test_tx_rx_hooks_have_no_fpu_or_api_calls(asm):
    code,syms=asm
    d=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
    for a,b in [('mp_rx_probe','mp_tx_stamp'),('mp_tx_stamp','mp_reply')]:
        block=code[syms[a]:syms[b]]
        ins=list(d.disasm(block,BASE+syms[a]))
        assert ins and sum(i.size for i in ins)==len(block)
        for i in ins:
            assert not i.mnemonic.startswith(('v','cdp','mcr','mrc'))
            assert i.mnemonic not in ('bl','blx','svc','bkpt')

def test_reply_signature_rejects_r02a():
    with pytest.raises(ValueError):probe.decode(struct.pack('<12I',1,2,3,4,5,6,7,8,9,10,11,0x52303241))


def test_rx_rejects_corrupt_checksum_without_overwriting_stock_frame(asm):
    m=Machine(asm)
    p=frame(m.u,base=0x20005000)
    m.u.mem_write(p+800,struct.pack('<I',0xF00D600D))
    m.u.mem_write(p+880,struct.pack('<4I',probe.CANARY,50,7,0))
    before=bytes(m.u.mem_read(p,1024))
    m.call('mp_rx_probe',{UC_ARM_REG_R1:p})
    assert bytes(m.u.mem_read(p,1024))==before
    assert m.counters()[4:11]==(1,probe.CANARY,50,7,0,0,1)

def test_rx_ignores_nonmatching_marker_even_if_other_words_match(asm):
    m=Machine(asm)
    p=frame(m.u,base=0x20005000)
    m.u.mem_write(p+800,struct.pack('<I',0xF00D600D))
    m.u.mem_write(p+880,struct.pack('<4I',0x11223344,50,7,0))
    m.call('mp_rx_probe',{UC_ARM_REG_R1:p})
    assert m.counters()[4:11]==(1,0x11223344,50,7,0,0,0)
