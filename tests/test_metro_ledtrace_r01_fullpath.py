"""Full donor binary LED-sender path, with M4LEDTRACE-R01 hook and clock stub.

Execute the *actual* rebuilt Entry 0 image from the final HXF. Compare return
semantics with the unchanged donor. Hardware I/O to the LED driver and hardware
microsecond timer are stubbed. No claim of physical boot or photon timing.
"""
from pathlib import Path
import pytest
import patch_amp as pa
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import (
 UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1,
 UC_ARM_REG_R2,UC_ARM_REG_R3)
from metro_ledtrace_r01_probe import TAG

DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
CANDIDATE=Path(__file__).parents[1]/'build/browser-ramrun/METRO-LEDSYNC-M4LEDTRACE-R01/METRO-LEDSYNC-M4LEDTRACE-R01.hxf'
STOP=0x28ff0000
SINK=0x28d9d72c
SEND=0x28d98f74
CLOCK=0x28da6458
FS3=0x28128a78
LED_VISIBLE=0x28e4daee

def sender(image,led=2,colour=0x0300ff,function=1,visible=1):
    archive,is_hxf=pa.load_l6ia_from_any(str(image))
    assert is_hxf
    e=pa.get_entry_swapped(archive,0)
    segs=pa._parse_e0_segments(e)
    uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    uc.mem_map(0x28000000,0x1000000)
    uc.mem_map(0x20000000,0x10000)
    for hdr,poff,length,base,nxt in segs:
        if 0x28000000<=base<0x29000000:
            uc.mem_write(base,e[poff:poff+length])
    uc.mem_write(STOP,b'\x00\xbf')
    uc.mem_write(FS3,bytes([function]))
    uc.mem_write(LED_VISIBLE,bytes([visible]))
    uc.mem_write(0x281c90a4,b'\x01\x01'+bytes(14))
    uc.reg_write(UC_ARM_REG_SP,0x2000f000)
    uc.reg_write(UC_ARM_REG_LR,STOP|1)
    uc.reg_write(UC_ARM_REG_R0,led)
    uc.reg_write(UC_ARM_REG_R1,colour)
    sink=[]
    clocks=[]
    def hook(u,addr,size,_):
        if addr==STOP:
            u.emu_stop()
        elif addr==SINK:
            sink.append((u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1)))
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR)|1)
        elif addr==CLOCK:
            clocks.append(u.reg_read(UC_ARM_REG_SP))
            u.reg_write(UC_ARM_REG_R0,0x12345678)
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR)|1)
    uc.hook_add(UC_HOOK_CODE,hook)
    uc.emu_start(SEND|1,STOP,count=25000)
    result=(uc.reg_read(UC_ARM_REG_PC),uc.reg_read(UC_ARM_REG_SP))
    return {'end':result,'sink':sink,'clock_stack':clocks}

@pytest.mark.parametrize('function,visible,colour',[
 (1,1,0x0300ff),(1,1,0),(2,1,0x0300ff),(1,0,0x0300ff),
 (1,1,0x003300),(1,1,0),
])
def test_full_original_m4_sender_returns_identically(function,visible,colour):
    donor=sender(DONOR,function=function,visible=visible,colour=colour)
    test=sender(CANDIDATE,function=function,visible=visible,colour=colour)
    assert test['end']==donor['end']==(STOP,0x2000f000)
    assert test['sink']==donor['sink']
    assert all(sp%8==0 for sp in test['clock_stack'])
    assert not donor['clock_stack']
    assert len(test['clock_stack'])<=1

def test_hxf_sharc_and_rest_of_original_exact():
    donor,_=pa.load_l6ia_from_any(str(DONOR))
    altered,_=pa.load_l6ia_from_any(str(CANDIDATE))
    assert all(pa.get_entry_swapped(donor,i)==pa.get_entry_swapped(altered,i) for i in range(1,15))
