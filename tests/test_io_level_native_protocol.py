"""Native RX payload parser tests grounded in physical R01 HW02 capture.

All tests use exact recorded packet hex structures; no pedal access. Enforce
disambiguation of stale RX buffer bytes after zero-length native payload.
"""
import struct,math
from io_level_native_protocol import parse_frame,unswap16

def w32(x):return unswap16(x)

def words(native_payload=(),seq=0x53):
    w=[0]*256
    w[0]=0xf00dface
    w[1]=((len(native_payload)&0xffff)<<16)|seq
    for k,v in enumerate(native_payload):
        w[2+k]=w32(v)
    w[255]=0xecafd00f
    return w

def meter_packet(db=(-70,-70,-120,-120,-120,-120,-81,-70)):
    ids=(2,5,3,6,4,6,1,5)
    native=[0x180000a8,0x03800110,0x04005400,0x00c1f0a4]
    for ch,v in zip(ids,db):
        native.extend([0,3,0x00020000,ch,struct.unpack('<I',struct.pack('<f',float(v)))[0]])
    assert len(native)==44
    return words(native)

def test_physical_HW02_native_meter_frame_yields_eight_correct_records():
    p=parse_frame(meter_packet())
    assert p['native_envelope_verified']
    assert p['native_payload_words']==44
    assert p['native_unclassified_trailing_words']==0
    records=p['native_full_records']
    assert len(records)==8
    assert [r['channel_id'] for r in records]==[2,5,3,6,4,6,1,5]
    assert {r['record_family'] for r in records}=={'0x00020000'}
    assert [r['value_float32'] for r in records]==[-70,-70,-120,-120,-120,-120,-81,-70]

def test_empty_native_message_never_decodes_persistent_past_native_meter_values():
    w=meter_packet()
    w[1]=0x00005318   # 0 native payload words, retain old 44 fields in DMA memory
    p=parse_frame(w)
    assert p['native_payload_words']==0
    assert not p['native_payload_nonempty']
    assert not p['native_envelope_verified']
    assert p['native_full_records']==[]

def test_actual_HW02_nonmeter_native_one_record_identified_separately():
    n=[0x1800001c,0x03800110,0x0400c500,0x00c1f0a4,
       0,3,0x0002002e,1,0xbf800000]
    p=parse_frame(words(n))
    assert p['native_envelope_verified'] and p['native_payload_words']==9
    assert len(p['native_full_records'])==1
    r=p['native_full_records'][0]
    assert (r['record_family'],r['channel_id'],r['value_float32'])==('0x0002002e',1,-1)

def test_actual_HW02_partial_native_event_declares_incomplete_tail():
    n=[0x1800002c,0x03800110,0x04004c00,0x00c1f0a4,
       0,3,0x0002002a,1,struct.unpack('<I',struct.pack('<f',-70.05063))[0],
       0,3,0x0002002a,2]
    p=parse_frame(words(n))
    assert p['native_envelope_verified']
    assert p['native_payload_words']==13
    assert len(p['native_full_records'])==1
    assert p['native_unclassified_trailing_words']==4
    assert p['native_full_records'][0]['record_family']=='0x0002002a'

def test_bad_native_payload_length_or_envelope_fails_closed():
    p=parse_frame(words([0x180000a8,0x03800110,0x04005400,0x00c1f0a4]))
    assert not p['native_envelope_verified']
    assert p['native_full_records']==[]
    assert p['native_error']=='native envelope type, flags or byte length mismatch'
    p=parse_frame(words([0]*254))
    assert not p['native_envelope_verified']
    assert 'native_error' in p

def test_raw_M4_RX_word_header_is_halfword_swapped():
    assert unswap16(0x00a81800)==0x180000a8
    assert unswap16(0x01100380)==0x03800110
