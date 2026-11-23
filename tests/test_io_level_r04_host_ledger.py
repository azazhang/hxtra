"""Read-only R04 host decoder; synthetic bytes use real R01 native IDs."""
import struct,pytest
from io_level_r04_native_ledger import decode,unswap32

def words(family=0x0002002a,param=1,vals=(-70,-81,-18),count=5):
    w=[0]*160
    w[0]=0x344d4f49
    w[1:7]=[5000,30,8,4,3,0x80001e1d]
    i=16
    enc=lambda x:unswap32(struct.unpack('<I',struct.pack('<f',float(x)))[0])
    w[i:i+6]=[unswap32(family),param<<16,enc(vals[0]),count,enc(vals[1]),enc(vals[2])]
    return struct.pack('<160I',*w)

def test_real_families_parsed_with_source_identity_unclaimed():
    r=decode(words())
    assert r['variant']=='IO-LEVEL-R04-FULL-NATIVE-EVENT-LEDGER'
    assert r['observed_record_keys']==1
    assert r['m4_RX_frames_seen']==5000 and r['native_nonempty_packets_seen']==30
    assert (r['bulk_left_pixels'],r['bulk_right_pixels'])==(29,30)
    rec=r['native_records'][0]
    assert (rec['object_family'],rec['parameter_id'])==('0x0002002a',1)
    assert (rec['observations'],rec['last'],rec['minimum'],rec['maximum'])==(5,-70,-81,-18)
    assert rec['range']==63
    assert r['record_to_physical_io_mapping_verified'] is False

def test_wrong_length_or_signature_fails():
    with pytest.raises(ValueError,match='640'):decode(b'')
    with pytest.raises(ValueError,match='signature'):decode(bytes(640))

def test_other_valid_native_family_and_stereo_parameter_id():
    r=decode(words(family=0x00020002,param=3,vals=(-88,-91,-70),count=12))
    x=r['native_records'][0]
    assert (x['object_family'],x['parameter_id'],x['observations'])==('0x00020002',3,12)
    assert (x['last'],x['minimum'],x['maximum'])==(-88,-91,-70)
