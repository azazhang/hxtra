"""R03C complete M4 Thumb -> SPI pair -> SHARC 142-word audio kernel tests."""
import json
import pytest
import test_click
from test_metro_led_r03b_transport import BMachine,kernel,packet
from test_metro_led_r03c_tap_grace import m4
from test_metro_led_r03c_ordered_receiver import code

TRACE='tests/hardware_evidence/METRO-LEDSYNC-M4LEDTRACE-R01-HWKNOB01-live.jsonl'

def count(c):return c.sim.rd(test_click.I0+21)
def last(c):return c.sim.rd(test_click.I0+28)

def test_real_unicorn_m4_to_real_ssim_SHARC_prevents_stale_ghost_and_transient_fallback(m4,code):
    sharc=code[0]
    m=BMachine(m4);m.prepare()
    c=kernel((sharc,),time=.5,accent=4)
    word,check=m.stamp()
    packet(c,word,check)
    c.call()
    assert count(c)==0
    m.emit(1,us=1_000_000)
    m.time_us=1_000_300
    word,check=m.stamp()
    assert word==0x80000001 and check==0x7ffffffe
    packet(c,word,check)
    first=c.call()+c.run(480)
    assert test_click.freq(first)==pytest.approx(2000,rel=.025)
    assert count(c)==1

    # Transient M4 status dropout is debounced: the SHARC sees only the
    # same validated event and cannot run its independent Time oscillator.
    m.set_tap(False)
    for i in range(45):
        assert m.stamp()==(word,check)
        packet(c,*m.stamp())
        c.call()
    assert count(c)==1
    m.set_tap(True)
    assert m.stamp()==(word,check)
    assert count(c)==1
    m.emit(0,us=1_270_000)
    m.emit(1,us=1_545_000)
    m.time_us=1_545_700
    word,check=m.stamp()
    assert word==0x80000002 and check==0x7ffffffd
    packet(c,word,check)
    second=c.call()+c.run(480)
    assert test_click.freq(second)==pytest.approx(1000,rel=.025)
    assert count(c)==2

    # A complete valid but old prior frame cannot generate ghost clicks.
    packet(c,0x80000001)
    c.call()
    assert count(c)==2 and last(c)==0x80000002
    packet(c,word,check)
    c.call()
    assert count(c)==2 and last(c)==0x80000002

    # Full pair mismatch cannot trigger or overwrite last good event.
    packet(c,0x80000003,checksum=0xBAD0BAD0)
    c.call()
    assert count(c)==2 and last(c)==0x80000002

    # Genuine next physical edge and epoch reset still work.
    m.emit(0,us=1_800_000)
    m.emit(1,us=2_090_000)
    m.time_us=2_090_250
    packet(c,*m.stamp())
    c.call()
    assert count(c)==3 and last(c)==0x80000003
    m.bypass(False)
    m.emit(0,us=2_300_000)
    m.emit(1,us=2_635_000)
    packet(c,*m.stamp())
    c.call()
    assert count(c)==3
    m.bypass(True)
    m.emit(0,us=2_900_000)
    m.emit(1,us=3_180_000)
    packet(c,*m.stamp())
    c.call()
    assert count(c)==1 and last(c)==4, 'fourth accepted edge toggles epoch on re-engage'

def test_replay_physical_620_event_steady_and_knob_trace_with_SHARC_consumer(m4,code):
    from pathlib import Path
    items=[json.loads(line) for line in Path(TRACE).read_text().splitlines() if line.strip()]
    events={e['sequence']:e for record in items for e in record.get('events',[])}
    assert len(events)==620
    m=BMachine(m4);m.prepare()
    c=kernel((code[0],),time=.545,accent=4)
    packet(c,*m.stamp());c.call()
    for seq in sorted(events):
        e=events[seq]
        m.emit(1 if e['led_lit'] else 0,us=e['timestamp_us_u32'])
        packet(c,*m.stamp())
        c.call()
    observed=m.ctrs()[0]
    assert observed==0x80000130,hex(observed)  # 304 ONs = 0x130
    assert m.ctrs()[4]==6
    assert last(c)==observed
    assert count(c)==0, '304 accepted beats % 4 leaves bar counter 0'
    assert not m.alignment_errors
