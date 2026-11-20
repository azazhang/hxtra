"""M4 actual donor LED sender through current R02C ISR/trampoline, on Unicorn."""
from pathlib import Path
import pytest
import patch_amp as pa
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE,UC_MODE_MCLASS
from unicorn.arm_const import *

SRC=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
PATCHED=Path('build/METRO-LEDSYNC-R02C-DONOR-EGRESS-OFFLINE.l6ia')
STOP=0x28ff0000
SINK=0x28d9d72c
SEND=0x28d98f74

def run(image,led=2,color=0x0300ff,function=1,visible=1):
    e=pa.get_entry_swapped(image,0)
    segs=pa._parse_e0_segments(e)
    uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    uc.mem_map(0x28000000,0x01000000)
    uc.mem_map(0x20000000,0x10000)
    for hdr,poff,length,base,nxt in segs:
        if 0x28000000<=base<0x29000000:
            uc.mem_write(base,e[poff:poff+length])
    uc.mem_write(STOP,b'\x00\xbf')
    uc.mem_write(0x28128a78,bytes([function]))
    uc.mem_write(0x28e4daee,bytes([visible]))
    # LED sender hardware context. First two bytes enable underlying driver.
    uc.mem_write(0x281c90a4,b'\x01\x01'+bytes(14))
    uc.reg_write(UC_ARM_REG_SP,0x2000f000)
    uc.reg_write(UC_ARM_REG_LR,STOP|1)
    uc.reg_write(UC_ARM_REG_R0,led)
    uc.reg_write(UC_ARM_REG_R1,color)
    history=[]
    def hook(u,addr,size,_):
        if addr in (SEND,0x28e4d632,0x28d98f78,0x28e60c00,SINK,STOP):
            history.append((hex(addr),hex(u.reg_read(UC_ARM_REG_SP)),hex(u.reg_read(UC_ARM_REG_R0))))
        if addr==STOP:u.emu_stop()
        if addr==SINK:
            # Hardware serial peripheral stub: caller can return.
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR)|1)
    uc.hook_add(UC_HOOK_CODE,hook)
    try:
        uc.emu_start(SEND|1,STOP,count=20000)
        result=(hex(uc.reg_read(UC_ARM_REG_PC)),hex(uc.reg_read(UC_ARM_REG_SP)))
        return result,history
    except Exception as ex:
        return repr(ex),history


def test_exact_installed_donor_led_path_vs_r02c_synchronous_context():
    original,_=pa.load_l6ia_from_any(str(SRC))
    candidate=PATCHED.read_bytes()
    for function,visible,rgb in [(1,1,0x0300ff),(1,1,0),(2,1,0x0300ff),(1,0,0x0300ff)]:
        a,ah=run(original,function=function,visible=visible,color=rgb)
        b,bh=run(candidate,function=function,visible=visible,color=rgb)
        print('case',function,visible,hex(rgb),'ORIGINAL',a,ah[-6:],'R02C',b,bh[-6:])
        assert b==a
