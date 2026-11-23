"""R06 assembled Cortex-M4: sixteen 7px segmented LEDs, max native peaks, bounded fall.

Tests are firmware-offline; no physical HX Stomp is modified. They verify
native event selection, independent 2-channel ballistics, real source peaks,
Home paint geometry/color, and the IOM6 read-only telemetry payload.
"""
import struct
import pytest
import m4asm
from m4emu import M4
from test_io_level_r04_full_native_ledger import (BASE,RX,FB,DRAW_FN,REGISTER_FN,SEND_FN,REQ,REDRAW_FN,native_packet,mkframe,ledger,symbol,bins)

@pytest.fixture(scope='module')
def module():
    return m4asm.assemble_module('src/m4/io_level_r06_segmented_peak_envelope.s')

@pytest.fixture
def machine(module):
    code,syms=module
    m=M4(code,BASE)
    m.syms=syms
    m.paint=[]; m.registration=[]; m.replies=[]
    m.stub(REDRAW_FN)
    def register(mm):
        m.registration.append((mm.reg('r0'),struct.unpack('<3I',mm.read(mm.reg('r1'),12))))
    def reply(mm):
        n=mm.stack_args(1)[0]
        m.replies.append((mm.reg('r0'),mm.reg('r1'),mm.reg('r2'),mm.read(mm.reg('r3'),n)))
    m.stub(REGISTER_FN,register)
    m.stub(SEND_FN,reply)
    def fill(mm):
        m.paint.append((mm.reg('r0'),mm.reg('r1'),mm.reg('r2'),mm.reg('r3'),*mm.stack_args(3)))
    m.stub(DRAW_FN,fill)
    return m

BLANK=mkframe(hdr=0)

def push(m,frame):
    m.write(RX,frame)
    m.call(symbol(m,'io_meter_frame'),0,RX)

def tick(m,n):
    for _ in range(n): push(m,BLANK)

def visual(m):
    x=m.u32(symbol(m,'io_display_state'))
    return x&255,(x>>8)&255

def pending(m):
    x=m.u32(symbol(m,'io_peak_pending'))
    return x&255,(x>>8)&255


def test_keeps_existing_two_native_R05_sources_and_latches_high_between_LCD_ticks(machine):
    m=machine
    push(m,native_packet(family=0x0002002a,param=1,db=-12))
    assert bins(m)==(0,114,True)
    assert pending(m)==(0,114)
    # A second low native event BEFORE UI tick must not erase that peak.
    push(m,native_packet(family=0x0002002a,param=1,db=-70))
    assert bins(m)==(0,29,True)
    assert pending(m)==(0,114)
    assert visual(m)==(0,0)
    tick(m,98)   # exactly 100 receive frames total -> one visual tick
    assert visual(m)==(0,114)
    assert pending(m)==(0,0)
    assert len(m.calls(REDRAW_FN))==1
    assert m.u32(symbol(m,'io_high_native_events')+4)==1
    assert m.u32(symbol(m,'io_redraw_requests'))==1


def test_native_peak_hold_and_fast_fall_are_per_channel_and_not_fake_tap(machine):
    m=machine
    push(m,native_packet(family=0x00020002,param=3,db=-32))
    push(m,native_packet(family=0x0002002a,param=1,db=-12))
    push(m,native_packet(family=0x0002002a,param=1,db=-70))
    push(m,native_packet(family=0x00020002,param=3,db=-88))
    tick(m,96)
    assert visual(m)==(85,114)
    assert m.u32(symbol(m,'io_display_holds'))==(2 |(2<<8))
    # Attack is immediate, hold two ~43ms ticks, then decay 12px per tick.
    tick(m,100)
    assert visual(m)==(85,114)
    tick(m,100)
    assert visual(m)==(85,114)
    tick(m,100)
    assert visual(m)==(73,102)
    tick(m,100)
    assert visual(m)==(61,90)
    # No native click was added: the visual state must never rise again.
    last=visual(m)
    for _ in range(6):
        tick(m,100)
        now=visual(m)
        assert now[0]<=last[0] and now[1]<=last[1]
        last=now
    assert visual(m)==(2,29)


def test_false_peaks_not_inferred_from_low_records_or_native_nonmeter_keys(machine):
    m=machine
    for i in range(5):
        push(m,native_packet(family=0x0002002a,param=1,db=-68))
        push(m,native_packet(family=0x0002002a,param=2,db=-2))
        push(m,native_packet(family=0x0002002e,param=1,db=-1))
    tick(m,85)
    assert visual(m)[0]==0 and visual(m)[1]<40
    assert pending(m)==(0,0)
    assert m.u32(symbol(m,'io_high_native_events')+4)==0
    assert len(ledger(m))==3


def test_ui_16_segment_gap_color_zones_and_original_small_Home_footprint(machine):
    m=machine
    # Force visual envelope full for both candidate meters (no DSP path change).
    m.u32(symbol(m,'io_display_state'),132|(132<<8))
    m.call(symbol(m,'io_meter_draw'),FB,0x2812a05c)
    fills=m.paint
    assert len(fills)==2+16+16
    bg=fills[:2]
    assert [(x[1],x[2],x[3],x[4],x[5]) for x in bg]==[(24,118,132,5,0x25282c),(164,118,132,5,0x25282c)]
    for base,items in ((24,fills[2:18]),(164,fills[18:34])):
        assert [x[1] for x in items]==[base+2+8*i for i in range(16)]
        assert all(x[2]==118 and x[3]==7 and x[4]==5 and x[6]==6 for x in items)
        assert [x[5] for x in items]==[0x35c878]*10 + [0xe9c84d]*3 + [0xf4a53a]*2 + [0xd94242]
        assert items[-1][1]+items[-1][3] <= base+132
    assert m.u32(symbol(m,'io_paint_count'))==1
    assert m.u32(symbol(m,'io_painted_hot_count'))==1
    assert m.u32(symbol(m,'io_last_painted_state'))==132|(132<<8)


def test_led_count_monotone_and_no_bogus_LED_when_zero(machine):
    m=machine
    for pixels,expected in ((0,0),(1,1),(8,1),(9,2),(29,4),(30,4),(85,11),(113,14),(114,14),(132,16)):
        m.paint.clear()
        m.u32(symbol(m,'io_display_state'),pixels)
        m.call(symbol(m,'io_meter_draw'),FB,0x2812a05c)
        assert len(m.paint)==2+expected,(pixels,len(m.paint),expected)
        assert all(x[1]<164 for x in m.paint[2:])


def test_R06_existing_readonly_0x13_640B_new_IOM6_paint_and_native_counters(machine):
    m=machine
    m.call(symbol(m,'io_diag_register'))
    assert m.registration[0][0]==0x13
    push(m,native_packet(family=0x0002002a,param=1,db=-12))
    push(m,native_packet(family=0x0002002a,param=1,db=-70))
    tick(m,98)
    m.call(symbol(m,'io_meter_draw'),FB,0x2812a05c)
    m.write(REQ+12,struct.pack('<H',0x4455))
    m.call(symbol(m,'io_diag_command'),0x20001700,REQ)
    stream,seq,status,reply=m.replies[0]
    assert (stream,seq,status)==(0x20001700,0x4455,0)
    assert len(reply)==643 and reply[:3]==bytes.fromhex('c50280')
    word=struct.unpack('<160I',reply[3:])
    assert word[0]==0x364d4f49
    assert word[5]==2 and word[6]==m.u32(symbol(m,'io_bar_state'))
    assert word[8]==1 and word[9]==1                       # paint, repaint request
    assert word[10]==word[11]==(114<<8)                    # painted and visible
    assert word[12]==0 and word[13]==1                     # native high left/right
    assert word[14]==0 and word[15]==1                     # pending cleared; hot paint
    assert word[16:22] == tuple(struct.unpack('<6I',m.read(symbol(m,'io_event_table'),24)))


def test_44word_old_source_does_not_override_or_trigger_fake_R06_peaks(machine):
    m=machine
    push(m,native_packet(family=0x0002002a,param=1,db=-12))
    push(m,mkframe(levels=(-70,-70,-120,-120,-120,-120,-81,-70)))
    assert pending(m)==(0,114)
    assert bins(m)==(0,114,True)
    assert m.u32(symbol(m,'io_diag_live')+16)==1
    assert len(ledger(m))>=7


def test_independent_stale_expiry_preserves_live_source_and_display_smooths_to_zero(machine):
    m=machine
    push(m,native_packet(family=0x00020002,param=3,db=-32))
    push(m,native_packet(family=0x0002002a,param=1,db=-12))
    age=symbol(m,'io_live_ages')
    m.u32(age,4599)
    m.u32(age+4,0)
    push(m,BLANK)
    assert bins(m)==(0,114,True)
    assert m.u32(age)==4600 and m.u32(age+4)==1
