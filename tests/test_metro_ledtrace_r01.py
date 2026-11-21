"""M4LEDTRACE-R01 actual Thumb execution, wire payload, and immutable-donor checks."""
import hashlib,struct,tempfile
from pathlib import Path
import pytest
import m4asm,usb_commands,patch_amp as pa
from test_metro_r02a_m4edge import Machine,BASE
from metro_ledtrace_r01_donor_patch import patch_donor,DONOR_MD5,DONOR_SHA256,PATCH_SITES
from metro_ledtrace_r01_probe import decode,DATA_BYTES,VARIANT
from unicorn.arm_const import (UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_R0,
 UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4)
from unicorn import UC_HOOK_CODE
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB

DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
FS3_FUNCTION=0x28128a78
TIMER=0x28da6458

@pytest.fixture(scope='module')
def assembled():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp,'usb.inc').write_text(usb_commands.inc('metronome_phase'))
        return m4asm.assemble_module('src/m4/metro_ledtrace_r01.s',include=(tmp,))

class TraceMachine(Machine):
    def __init__(self,assembled):
        self.time_us=1000000
        self.clock_reads=0
        self.alignment_errors=[]
        super().__init__(assembled)
    def on_code(self,uc,address,size,user_data):
        if address==TIMER:
            self.clock_reads+=1
            if uc.reg_read(UC_ARM_REG_SP)%8:
                self.alignment_errors.append(uc.reg_read(UC_ARM_REG_SP))
            uc.reg_write(UC_ARM_REG_R0,self.time_us&0xffffffff)
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR)|1)
        else:
            super().on_code(uc,address,size,user_data)
    def set_tap(self,enabled=True):
        self.uc.mem_write(FS3_FUNCTION,b'\x01' if enabled else b'\x02')
    def emit(self,colour,idx=2,us=None):
        if us is not None:self.time_us=us
        return self.call('mt_capture',r0=idx,r1=colour)
    def snapshot(self):
        self.call('mt_register')
        assert self.registered[0]==0x50
        request=0x20001000
        self.uc.mem_write(request+0xc,struct.pack('<H',0x1234))
        self.call('mt_command',r0=0x20002000,r1=request)
        assert self.sent[:3]==(0x20002000,0x1234,0)
        assert self.sent[3][:2]==bytes([0xc4,DATA_BYTES])
        return self.sent[3][2:]

def test_donor_exact_two_sites_and_all_original_SHARC_bytes():
    raw=DONOR.read_bytes()
    assert hashlib.md5(raw).hexdigest()==DONOR_MD5
    assert hashlib.sha256(raw).hexdigest()==DONOR_SHA256
    archive,is_hxf=pa.load_l6ia_from_any(str(DONOR))
    assert is_hxf
    new,info=patch_donor(archive)
    assert info['patch_sites']==[hex(n) for n in PATCH_SITES]
    assert info['original_non_M4_entries_byte_identical']==14
    assert info['disallowed_original_M4_modifications']==0
    assert info['modified_entry0_bytes']-info['original_entry0_bytes']<700
    for i in range(1,15):
        assert pa.get_entry_swapped(new,i)==pa.get_entry_swapped(archive,i)

def test_visible_LED_rising_and_falling_timestamps_and_dedup(assembled):
    m=TraceMachine(assembled);m.set_tap()
    m.emit(0x0300ff,idx=1,us=100) # another LED
    m.emit(0x0300ff,us=1000000)
    m.emit(0x1234ff,us=1000001) # colour-only update, still lit
    m.emit(0,us=1300000)
    m.emit(0,us=1300001)
    m.emit(0x0300ff,us=1600000)
    result=decode(m.snapshot())
    assert m.clock_reads==3
    assert result['total_transitions']==3
    assert [v['led_lit'] for v in result['events']]==[True,False,True]
    assert [v['timestamp_us_u32'] for v in result['events']]==[1000000,1300000,1600000]
    assert [v['interval_us'] for v in result['events'][1:]]==[300000,300000]
    assert result['currently_lit'] and not m.alignment_errors
    assert result['revision']==VARIANT

def test_non_tap_mode_resets_state_without_clock_or_record(assembled):
    m=TraceMachine(assembled)
    m.set_tap();m.emit(1,us=100)
    m.set_tap(False);m.emit(1,us=200)
    m.set_tap(True);m.emit(1,us=300)
    result=decode(m.snapshot())
    assert [v['timestamp_us_u32'] for v in result['events']]==[100,300]
    assert m.clock_reads==2

def test_ring_wrap_tracks_last_sixteen_transitions(assembled):
    m=TraceMachine(assembled);m.set_tap()
    for i in range(24):
        m.emit(0x0300ff if i%2==0 else 0,us=1000000+i*250000)
    result=decode(m.snapshot())
    assert result['total_transitions']==24
    assert len(result['events'])==16
    assert [v['sequence'] for v in result['events']]==list(range(9,25))
    assert [v['interval_us'] for v in result['events'][1:]]==[250000]*15
    assert not result['currently_lit']

def test_32bit_microsecond_clock_wrap_is_decoded_modulo(assembled):
    m=TraceMachine(assembled);m.set_tap()
    m.emit(1,us=0xfffffff0);m.emit(0,us=0x10)
    assert decode(m.snapshot())['events'][1]['interval_us']==32

def test_torn_or_writer_active_USB_read_is_rejected(assembled):
    m=TraceMachine(assembled);m.set_tap();m.emit(1)
    response=bytearray(m.snapshot())
    struct.pack_into('<I',response,4,3) # busy generation
    with pytest.raises(ValueError,match='unstable'):
        decode(bytes(response))
    response=bytearray(m.snapshot())
    struct.pack_into('<I',response,DATA_BYTES-4,4) # different even generation
    with pytest.raises(ValueError,match='unstable'):
        decode(bytes(response))
    response=bytearray(m.snapshot());response[0]^=0xff
    with pytest.raises(ValueError,match='signature'):
        decode(bytes(response))

def test_realtime_paths_no_fp_or_stock_locking_and_clock_is_whitelisted(assembled):
    data,syms=assembled
    dis=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
    for start,end in [('mt_led_entry','mt_capture'),('mt_capture','mt_register')]:
        code=data[syms[start]:syms[end]]
        ins=list(dis.disasm(code,BASE+syms[start]))
        assert ins and sum(i.size for i in ins)==len(code)
        assert all(not i.mnemonic.startswith(('vldr','vstr','vmov','vadd','vcmp','vdiv','vmul')) for i in ins)
        assert all(i.mnemonic not in ('svc','bkpt') for i in ins)
    m=TraceMachine(assembled);m.set_tap()
    m.emit(1);assert m.clock_reads==1 and not m.alignment_errors

def test_led_trampoline_preserves_donor_continuation(assembled):
    m=TraceMachine(assembled);m.set_tap()
    node=0x20003000;m.uc.mem_write(node,b'\x01'+bytes(15))
    continuation=0x28d98f7c
    m.uc.mem_write(continuation,b'\x70\x47')
    observed=[]
    def original(uc,address,size,user):
        if address!=continuation:return
        observed.append((uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1),
                         uc.reg_read(UC_ARM_REG_R2),uc.reg_read(UC_ARM_REG_R3),
                         uc.reg_read(UC_ARM_REG_SP)))
        uc.reg_write(UC_ARM_REG_SP,uc.reg_read(UC_ARM_REG_SP)+20)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR)|1)
    m.uc.hook_add(UC_HOOK_CODE,original)
    m.call('mt_led_entry',r0=2,r1=0x0300ff,r2=42,r3=node)
    assert observed==[(2,0x0300ff,1,node,0x2000f000-20)]
    assert m.uc.reg_read(UC_ARM_REG_SP)==0x2000f000
    assert decode(m.snapshot())['total_transitions']==1
