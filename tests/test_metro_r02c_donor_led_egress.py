"""R02C: execute M4 LED egress counter in Unicorn, preserve exact installed donor.

M4-only prototype; no claim of actual SHARC click synchronization, and no
physical pedal firmware load. Lighting is represented by the final LED sender
RGB, after the donor's tap-visibility filter.
"""
from pathlib import Path
import hashlib,struct,tempfile
import pytest
import m4asm,usb_commands
from test_metro_r02a_m4edge import Machine,BASE
from metro_led_donor_patch import DONOR_MD5,DONOR_SHA256,donor_patch
import patch_amp as pa

DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
FS3_FUNCTION=0x28128a78
TAP_LED_VISIBLE=0x28e4daee

def put_in_tap_mode(m):
    m.uc.mem_write(FS3_FUNCTION,b'\x01')
    m.uc.mem_write(TAP_LED_VISIBLE,b'\x01')


@pytest.fixture(scope='module')
def m4():
    with tempfile.TemporaryDirectory() as d:
        (Path(d)/'usb.inc').write_text(usb_commands.inc('metronome_phase'))
        return m4asm.assemble_module('src/m4/metronome_led_egress.s',include=(d,))


def test_only_real_fs3_dark_to_lit_bus_output_increments_counter(m4):
    m=Machine(m4)
    put_in_tap_mode(m)
    m.call('mp_bypass',r1=8,r2=0)  # physical preset 41C Metronome engaged
    emit=lambda index,color:m.call('mp_led_capture',r0=index,r1=color)
    assert m.counters()[0]==0
    emit(0,0x0300ff) # another footswitch LED, no click
    emit(1,0x0300ff)
    assert m.counters()[0]==0
    emit(2,0x0300ff) # actual FS3 LED dark->lit
    assert m.counters()[0]==0x80000001  # first visible beat toggles re-enable flag
    for _ in range(5):emit(2,0x0300ff) # no repeat for same lit command
    emit(2,0x00ff84) # changing colour while lit still one flash
    assert m.counters()[0]==0x80000001
    emit(2,0) # dark
    emit(2,0) # double dark
    emit(2,0x0300ff)
    assert m.counters()[0]==0x80000002
    assert m.counters()[-1]==0x43324352


def test_bpm_led_off_visibility_suppresses_events(m4):
    m=Machine(m4)
    put_in_tap_mode(m)
    m.call('mp_bypass',r1=8,r2=0)
    m.call('mp_led_capture',r0=2,r1=0) # donor BPM wrapper filtered the colour to black
    m.call('mp_led_capture',r0=2,r1=0)
    assert m.counters()[0]==0
    m.call('mp_led_capture',r0=2,r1=0x0300ff) # visibility re-enabled
    assert m.counters()[0]==0x80000001


def test_external_mode2_blink_bus_pulses_count_one_each(m4):
    m=Machine(m4)
    put_in_tap_mode(m)
    m.call('mp_bypass',r1=8,r2=0)
    for i in range(7):
        m.call('mp_led_capture',r0=2,r1=0x0300ff)
        m.call('mp_led_capture',r0=2,r1=0)
    assert m.counters()[0]==0x80000007


def test_bypass_callback_preserves_old_donor_processing_and_counts_reentry(m4):
    m=Machine(m4)
    put_in_tap_mode(m)
    for slot,bypass in [(7,0),(8,1),(8,0),(8,0)]:
        m.call('mp_bypass',r1=slot,r2=bypass)
    assert m.counters()[1]==2


def test_donor_direct_patch_modifies_only_five_hook_sites_and_appended_code():
    original=DONOR.read_bytes()
    assert hashlib.md5(original).hexdigest()==DONOR_MD5
    assert hashlib.sha256(original).hexdigest()==DONOR_SHA256
    archive,_=pa.load_l6ia_from_any(str(DONOR))
    updated,record=donor_patch(archive)
    assert record['untouched_other_entries']==14
    assert record['disallowed_m4_byte_mutations']==0
    assert record['entry0_new']-record['entry0_old']<2048
    for entry in range(1,15):
        assert pa.get_entry_swapped(archive,entry)==pa.get_entry_swapped(updated,entry)
    e0=pa.get_entry_swapped(updated,0)
    for marker in (b'DSP Usage Display',b'Breathing Line',b'Path A',b'Main+Snd',b'FS1 Hold'):
        assert marker in e0


def test_no_on_events_published_during_bypass_and_next_edge_resets_bar(m4):
    m=Machine(m4)
    put_in_tap_mode(m)
    m.call('mp_bypass',r1=8,r2=1) # initially bypassed 41C Metronome
    for i in range(3):
        m.call('mp_led_capture',r0=2,r1=0x0300ff)
        m.call('mp_led_capture',r0=2,r1=0)
    assert m.counters()[0]==0
    m.call('mp_bypass',r1=8,r2=0)
    m.call('mp_led_capture',r0=2,r1=0x0300ff)
    assert m.counters()[0]==0x80000001  # first audible click accented
    m.call('mp_led_capture',r0=2,r1=0)
    m.call('mp_led_capture',r0=2,r1=0x0300ff)
    assert m.counters()[0]==0x80000002
    m.call('mp_bypass',r1=8,r2=1)
    m.call('mp_led_capture',r0=2,r1=0)
    m.call('mp_led_capture',r0=2,r1=0x0300ff)
    assert m.counters()[0]==0x80000002, 'bypassed LED flashes must not queue later off-grid clicks'
    m.call('mp_bypass',r1=8,r2=0)
    m.call('mp_led_capture',r0=2,r1=0)
    assert m.counters()[0]==0x80000002, 're-engage itself does not trigger an off-grid click'
    m.call('mp_led_capture',r0=2,r1=0x0300ff)
    assert m.counters()[0]==3, 'third actual visible LED event toggles re-enable marker back to 0'


def test_preset_mode_led_changes_never_generate_tap_events(m4):
    m=Machine(m4)
    # FS3 defaults to a non-TAP mode in this test's image (zero).
    for col in (0x0300ff,0,0x0300ff,0,0x0300ff):
        m.call('mp_led_capture',r0=2,r1=col)
    assert m.counters()[0]==0
    put_in_tap_mode(m)
    m.call('mp_led_capture',r0=2,r1=0x0300ff)
    assert m.counters()[0]==0x80000001
    m.uc.mem_write(FS3_FUNCTION,b'\x02')
    m.call('mp_led_capture',r0=2,r1=0x0300ff)
    put_in_tap_mode(m)
    m.call('mp_led_capture',r0=2,r1=0x0300ff)
    assert m.counters()[0]==0x80000002, 'the next visible TAP illumination must be recognized after leaving Preset mode'


def test_spi_transport_stamps_only_real_tap_footwitch_mode(m4):
    m=Machine(m4)
    frame=0x20002000
    data=bytearray(1024)
    struct.pack_into('<I',data,0,0xFACEF00D)
    struct.pack_into('<I',data,4,48)
    struct.pack_into('<I',data,1020,0xD00FECAF)
    m.uc.mem_write(frame,bytes(data))
    # Preset mode FS3: this must disable the external master to preserve
    # original local metronome timing in other footswitch modes.
    m.call('mp_tx_stamp',r1=frame)
    assert struct.unpack('<I',m.uc.mem_read(frame+960,4))[0]==0
    put_in_tap_mode(m)
    m.call('mp_led_capture',r0=2,r1=0x0300ff)
    m.call('mp_tx_stamp',r1=frame)
    vals=struct.unpack('<4I',m.uc.mem_read(frame+960,16))
    assert vals[0]==0x4d543242
    assert vals[1]==0x80000001
    assert vals[2]==0
    assert vals[3]==(~(vals[0]^vals[1]^vals[2]))&0xffffffff
    # Exiting TAP mode invalidates old marker even if the buffer still holds
    # a valid previous packet, preventing stale LED timing from taking over.
    m.uc.mem_write(FS3_FUNCTION,b'\x02')
    m.call('mp_tx_stamp',r1=frame)
    assert struct.unpack('<I',m.uc.mem_read(frame+960,4))[0]==0
    assert m.counters()[2]==1
    assert m.counters()[3]==2


def test_invisible_TAP_led_disables_external_phase_and_retains_original_donor_local_click(m4):
    m=Machine(m4)
    frame=0x20002000
    data=bytearray(1024)
    struct.pack_into('<I',data,0,0xFACEF00D)
    struct.pack_into('<I',data,4,48)
    struct.pack_into('<I',data,1020,0xD00FECAF)
    m.uc.mem_write(frame,bytes(data))
    put_in_tap_mode(m)
    # Donor's BPM display code has the exact same visibility byte. When
    # setting 26 is Off it outputs black and the SHARC must retain local audio.
    m.uc.mem_write(TAP_LED_VISIBLE,b'\x00')
    m.call('mp_tx_stamp',r1=frame)
    assert struct.unpack('<I',m.uc.mem_read(frame+960,4))[0]==0
    m.uc.mem_write(TAP_LED_VISIBLE,b'\x01')
    m.call('mp_tx_stamp',r1=frame)
    assert struct.unpack('<I',m.uc.mem_read(frame+960,4))[0]==0x4d543242


def test_real_trampoline_preserves_donor_led_sender_registers_and_continuation(m4):
    # Execute the exact extra Thumb entry before the original donor sender's
    # remaining code. The test intercepts the unchanged continuation; it
    # validates the displaced sub SP,#20 and LDRB r2,[r3] plus register/stack
    # behavior, rather than testing only the helper counter in isolation.
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4
    m=Machine(m4)
    put_in_tap_mode(m)
    node=0x20003000
    m.uc.mem_write(node,b'\x01'+bytes(15))
    end=0x28d98f7c
    m.uc.mem_write(end,b'\x70\x47')
    visited=[]
    def original_continuation(uc,address,size,_):
        if address!=end:return
        visited.append({
            'r0':uc.reg_read(UC_ARM_REG_R0),
            'r1':uc.reg_read(UC_ARM_REG_R1),
            'r2':uc.reg_read(UC_ARM_REG_R2),
            'r3':uc.reg_read(UC_ARM_REG_R3),
            'r4':uc.reg_read(UC_ARM_REG_R4),
            'sp':uc.reg_read(UC_ARM_REG_SP)})
        # Return from the original 20-byte stack frame, simulating the
        # rest of the untouched donor's LED sender.
        uc.reg_write(UC_ARM_REG_SP,uc.reg_read(UC_ARM_REG_SP)+20)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR)|1)
    m.uc.hook_add(UC_HOOK_CODE,original_continuation)
    initial_sp=0x2000f000
    m.call('mp_led_entry',r0=2,r1=0x0300ff,r2=0x8877,r3=node)
    assert len(visited)==1
    assert visited[0]=={'r0':2,'r1':0x0300ff,'r2':1,'r3':node,'r4':0,'sp':initial_sp-20}
    assert m.uc.reg_read(UC_ARM_REG_SP)==initial_sp
    assert m.counters()[0]==0x80000001
