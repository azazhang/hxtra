"""R06 IOM6 640-byte telemetry: native records unaffected, paint fields accurate."""
import struct
import pytest
from io_level_r06_peak_telemetry import decode,unswap32

def raw(db):
    return unswap32(struct.unpack('<I',struct.pack('<f',float(db)))[0])

def payload():
    w=[0]*160
    w[:16]=[0x364d4f49,4000,101,3,3,22,0x8000721e,0,13,12,0x00721e,0x00721e,4,9,0x00002304,6]
    w[16:22]=[unswap32(0x0002002a),0x00010000,raw(-12.3),40,raw(-71),raw(-12.1)]
    w[22:28]=[unswap32(0x00020002),0x00030000,raw(-88),60,raw(-91),raw(-25)]
    return struct.pack('<160I',*w)

def test_IOM6_640Byte_paint_event_and_current_visual_record():
    a=decode(payload())
    assert a['variant']=='IO-LEVEL-R06-SEGMENTED-LED-PEAK-ENVELOPE'
    assert a['m4_RX_frames_seen']==4000
    assert a['bulk_right_pixels']==114 and a['bulk_left_pixels']==30
    assert a['home_paint_callback_count']==13 and a['stock_redraw_requests_count']==12
    assert (a['last_painted_left_pixels'],a['last_painted_right_pixels'])==(30,114)
    assert (a['display_left_pixels'],a['display_right_pixels'])==(30,114)
    assert (a['native_high_input_events'],a['native_high_output_events'])==(4,9)
    assert (a['peak_pending_left_pixels'],a['peak_pending_right_pixels'])==(4,35)
    assert a['paint_callbacks_with_high_output']==6
    assert a['actual_LCD_transfer_completion_measured'] is False
    assert a['observed_record_keys']==2
    assert a['native_records'][0]['object_family']=='0x0002002a'
    assert a['native_records'][0]['parameter_id']==1
    assert a['native_records'][0]['last']==pytest.approx(-12.3,abs=1e-5)
    assert a['native_records'][1]['object_family']=='0x00020002'
    assert a['native_records'][1]['parameter_id']==3

def test_wrong_magic_or_truncated_payload_rejected():
    with pytest.raises(ValueError,match='signature'):decode(bytes(640))
    with pytest.raises(ValueError,match='640'):decode(payload()[:639])

def test_old_IOM4_diagnostic_is_rejected_not_misdecoded_as_paint():
    data=bytearray(payload())
    struct.pack_into('<I',data,0,0x344d4f49)
    with pytest.raises(ValueError,match='IOM6'):decode(bytes(data))
