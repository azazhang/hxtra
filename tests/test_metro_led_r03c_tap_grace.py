"""R03C M4 TAP-loss grace and SPI packet continuity with actual Thumb code."""
from pathlib import Path
import tempfile,struct
import pytest
import m4asm,usb_commands
from test_metro_led_r03b_transport import BMachine,FRAME,TAP_LED_VISIBLE

ROOT=Path(__file__).parents[1]

@pytest.fixture(scope='module')
def m4():
    with tempfile.TemporaryDirectory() as d:
        Path(d,'usb.inc').write_text(usb_commands.inc('metronome_phase'))
        module=m4asm.assemble_module('src/m4/metronome_led_r03c.s',include=(d,))
        assert 'mp_no_tap_streak' in module[1]
        return module

def set_streak(m,n):
    base=0x28e70000+m.sym['mp_no_tap_streak']
    m.uc.mem_write(base,struct.pack('<I',n))

def get_streak(m):
    return struct.unpack('<I',m.uc.mem_read(0x28e70000+m.sym['mp_no_tap_streak'],4))[0]

def test_initial_non_TAP_preserves_stock_local_clock(m4):
    m=BMachine(m4);m.prepare()
    m.set_tap(False)
    assert get_streak(m)==4600
    assert m.stamp()==(0,0)
    assert m.ctrs()[9]==1
    assert m.ctrs()[5]==1

def test_transient_no_TAP_frame_holds_last_good_event_without_local_fallback(m4):
    m=BMachine(m4);m.prepare()
    assert m.stamp()==(0,0xffffffff)
    m.emit(1,us=1000000)
    assert m.stamp()==(0x80000001,0x7ffffffe)
    m.set_tap(False)
    for i in range(18):
        assert m.stamp()==(0x80000001,0x7ffffffe)
    assert get_streak(m)==18
    assert m.ctrs()[8]==18 and m.ctrs()[9]==0
    m.set_tap(True)
    assert m.stamp()==(0x80000001,0x7ffffffe)
    assert get_streak(m)==0
    assert m.ctrs()[10]==0

def test_sustained_mode_switch_restores_native_fallback_then_relocks(m4):
    m=BMachine(m4);m.prepare()
    m.emit(1,us=1000000)
    assert m.stamp()==(0x80000001,0x7ffffffe)
    m.set_tap(False)
    set_streak(m,4598)
    assert m.stamp()==(0x80000001,0x7ffffffe)
    assert get_streak(m)==4599
    assert m.stamp()==(0x80000001,0x7ffffffe)
    assert get_streak(m)==4600
    assert m.stamp()==(0,0)
    assert m.ctrs()[9]==1
    m.set_tap(True)
    assert m.stamp()==(0x80000001,0x7ffffffe)
    assert m.ctrs()[10]==0
    m.emit(0,us=1200000)
    m.emit(1,us=1545000)
    assert m.stamp()==(0x80000002,0x7ffffffd)

def test_visibility_toggle_holds_packet_for_grace_window(m4):
    m=BMachine(m4);m.prepare()
    m.emit(1,us=1000000)
    old=m.stamp()
    m.uc.mem_write(TAP_LED_VISIBLE,b'\0')
    for _ in range(15):assert m.stamp()==old
    m.uc.mem_write(TAP_LED_VISIBLE,b'\1')
    assert m.stamp()==old
    assert get_streak(m)==0

def test_short_dark_reversals_and_external_epoch_behavior_unchanged(m4):
    m=BMachine(m4);m.prepare()
    m.emit(1,us=1000000)
    assert m.stamp()==(0x80000001,0x7ffffffe)
    m.emit(0,us=1100000)
    m.emit(1,us=1101870)
    assert m.ctrs()[4]==1 and m.stamp()==(0x80000001,0x7ffffffe)
    m.emit(0,us=1400000)
    m.emit(1,us=1600000)
    assert m.stamp()==(0x80000002,0x7ffffffd)
    m.bypass(False)
    m.emit(0,us=1800000)
    m.emit(1,us=2050000)
    assert m.stamp()==(0x80000002,0x7ffffffd)
    m.bypass(True)
    m.emit(0,us=2200000)
    m.emit(1,us=2545000)
    assert m.stamp()==(3,0xfffffffc)


def test_native_M4_time_between_accepted_LED_request_and_first_SPI_stamp(m4):
    m=BMachine(m4);m.prepare()
    m.emit(1,us=1234567)
    m.time_us=1235267  # 700us after post-filter LED ON request
    assert m.stamp()==(0x80000001,0x7ffffffe)
    def rd(name):
        a=0x28e70000+m.sym[name]
        return struct.unpack('<I',m.uc.mem_read(a,4))[0]
    assert rd('mp_last_led_us')==1234567
    assert rd('mp_last_sent_event')==0x80000001
    assert rd('mp_last_led_to_tx_us')==700
    m.time_us=2235267 # subsequent frames do not retrigger timestamp
    m.stamp()
    assert rd('mp_last_led_to_tx_us')==700
    assert not m.alignment_errors, 'stock microsecond timer must run at aligned SP'

def test_readonly_extended_USB_0x50_84bytes_and_M4_flags(m4):
    from metro_led_r03c_probe import decode,DATA_BYTES,SIGNATURE
    m=BMachine(m4);m.prepare()
    m.emit(1,us=567890)
    m.time_us=568245
    m.stamp()
    m.call('mp_register')
    assert m.registered[0]==0x50
    request=0x20001000
    m.uc.mem_write(request+0xc,struct.pack('<H',0x1234))
    m.call('mp_command',r0=0x20004000,r1=request)
    assert m.sent[:3]==(0x20004000,0x1234,0)
    assert m.sent[3][:2]==bytes((0xc4,DATA_BYTES))
    r=decode(m.sent[3][2:])
    assert r['revision']=='METRO-LEDSYNC-R03C-HWGLITCH-REPAIR'
    assert r['LED_on_count_low31']==1
    assert r['M4_final_LED_state_lit']
    assert r['M4_Metronome_active_flag']
    assert r['M4_nonTAP_actual_streak']==0
    assert r['last_M4_LED_request_to_first_SPI_TX_us']==355
    assert r['M4_latency_measure_valid']
    assert not r['SHARC_consumer_counter_measured']
    corrupted=bytearray(m.sent[3][2:])
    struct.pack_into('<I',corrupted,44,0)
    with pytest.raises(ValueError,match='revision signature'):decode(bytes(corrupted))

def test_bounded_spi_payload_guard_never_modifies_unknown_frame(m4):
    m=BMachine(m4);m.prepare()
    m.uc.mem_write(FRAME+960,struct.pack('<2I',0x11111111,0x22222222))
    m.uc.mem_write(FRAME+4,struct.pack('<I',240))
    m.call('mp_tx_stamp',r1=FRAME)
    assert struct.unpack('<2I',m.uc.mem_read(FRAME+960,8))==(0x11111111,0x22222222)
    assert m.ctrs()[3]==1
