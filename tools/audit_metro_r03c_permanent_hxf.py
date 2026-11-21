#!/usr/bin/env python3
"""Fail-closed offline HXF audit before any Line 6 Updater persistent write.

Verifies the exact physical R03C HWGOOD01 .hxf against its exact HXtra
v1.2.1 donor: container integrity, payload/archive checksums, coherent
Updater dinf records, complete P36Updater trailer, bootloader & thirteen
other donor entries preserved, and exact original 142-word SHARC PM record
topology. This CANNOT prove an Updater handshake succeeds or on-device
flash/boot from persistent eMMC; that is a separate hardware acceptance.
No HX Stomp/USB access or firmware/device writes.
"""
from pathlib import Path
import hashlib,json,struct,sys,zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/sharc')]
import hxf,l6ia,patch_amp as pa,sasm
from metro_led_sharc_patch import parse_ldr

DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
CAND=ROOT/'build/browser-ramrun/METRO-LEDSYNC-R03C-HWGLITCH-REPAIR/METRO-LEDSYNC-R03C-HWGLITCH-REPAIR.hxf'
UNPACKED=CAND.with_suffix('.l6ia')
EXPECTED_DONOR_SHA256='96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0'
EXPECTED_CAND_SHA256='42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b'

def sha(data):return hashlib.sha256(data).hexdigest()

def check_hxf(raw):
    assert raw[:4]==b'FORM' and raw[8:12]==b'L6FF'
    assert struct.unpack_from('>I',raw,4)[0]==len(raw)-8
    chunks=hxf._chunks(raw)
    assert [x[0] for x in chunks]==[b'HEAD',b'dinf',b'dinf',b'data']
    head=chunks[0][3]
    assert len(head)==52
    assert chunks[-1][1]+8+chunks[-1][2]+(chunks[-1][2]&1)==len(raw)
    dinfs=[struct.unpack('>4I',x[3]) for x in chunks[1:3]]
    assert dinfs[0][:2]==(0,0x10000) and dinfs[1][:2]==(5,0x10000)
    body=zlib.decompress(chunks[-1][3])
    assert struct.unpack_from('>I',head,16)[0]==len(body)
    assert hashlib.md5(body).digest()==head[20:36]
    assert dinfs[0][2]==0
    assert dinfs[0][3]==dinfs[1][2]
    assert dinfs[0][3]+dinfs[1][3]==len(body)
    return {'head':head,'body':body,'dinfs':dinfs,'length':len(raw)}

def audit(donor=DONOR,candidate=CAND):
    d=Path(donor).read_bytes();c=Path(candidate).read_bytes()
    assert sha(d)==EXPECTED_DONOR_SHA256,(sha(d),'wrong donor')
    assert sha(c)==EXPECTED_CAND_SHA256,(sha(c),'wrong tested candidate')
    a=check_hxf(d);b=check_hxf(c)
    h0,h1=a['head'],b['head']
    assert h0[:16]==h1[:16], 'HXF firmware identity/version/product header changed'
    assert h0[36:]==h1[36:], 'Unexpected HEAD metadata changed'
    assert a['dinfs'][1][3]==b['dinfs'][1][3]
    assert a['body'][a['dinfs'][1][2]:]==b['body'][b['dinfs'][1][2]:], 'P36Updater trailer changed'
    assert b['body']==UNPACKED.read_bytes(), 'HXF payload differs from independently checked unpacked archive'
    da,ca=l6ia.parse(a['body']),l6ia.parse(b['body'])
    assert len(da)==len(ca)==15
    assert [e['index'] for e in da]==[e['index'] for e in ca]==list(range(15))
    changed=[i for i in range(15) if pa.get_entry_swapped(a['body'],i)!=pa.get_entry_swapped(b['body'],i)]
    assert changed==[0,2],changed
    assert (da[1]['type'],da[1]['words'],da[1]['sub'],da[1]['payload_len'])==(ca[1]['type'],ca[1]['words'],ca[1]['sub'],ca[1]['payload_len']), 'Bootloader entry fields changed'
    # Absolute header offsets differ by a few bytes only if earlier entry
    # changed size; since app is a same-size patch, all headers are equal.
    for i in range(15):
        if i in (0,2):continue
        x=da[i];y=ca[i]
        assert x['type']==y['type']
        assert x['sub']==y['sub']
        assert pa.get_entry_swapped(a['body'],i)==pa.get_entry_swapped(b['body'],i)
    assert da[2]['payload_len']==ca[2]['payload_len']==524212
    old_ldr=a['body'][da[2]['payload_off']:da[2]['payload_off']+524212]
    new_ldr=b['body'][ca[2]['payload_off']:ca[2]['payload_off']+524212]
    blocks0,pre0,tail0=parse_ldr(old_ldr)
    blocks1,pre1,tail1=parse_ldr(new_ldr)
    assert len(blocks0)==len(blocks1)==201
    assert pre0==pre1 and tail0==tail1
    assert [i for i,(u,v) in enumerate(zip(blocks0,blocks1)) if u!=v]==[177]
    assert all(u[:3]==v[:3] for u,v in zip(blocks0,blocks1))
    assert blocks0[177][:3]==blocks1[177][:3]==(5,142,0xe5386)
    assert zlib.crc32(pa.get_entry_swapped(b['body'],2))==ca[2]['crc32']
    # Core M4 app CRC is checked by l6ia_verify and build tool, repeated here.
    m4=pa.get_entry_swapped(b['body'],0)
    assert struct.unpack_from('<I',m4,8)[0]==zlib.crc32(m4[0x34:struct.unpack_from('<I',m4,4)[0]])
    assert zlib.crc32(pa.get_entry_swapped(b['body'],0))==ca[0]['crc32']
    return {
       'candidate_hxf':str(candidate),'size_bytes':len(c),
       'candidate_SHA256':sha(c),'donor_SHA256':sha(d),
       'product_HEAD_unchanged':True,
       'hxf_MD5_correct':True,'HXF_FORM_size_correct':True,
       'Updater_dinf_ranges_valid':True,
       'P36Updater_trailer_bytes_original':len(a['body'])-a['dinfs'][1][2],
       'P36Updater_trailer_byte_identical':True,
       'all_15_entries_present':True,
       'modified_entries':[0,2],
       'bootloader_entry1_unchanged':True,
       'other_13_entries_unchanged':True,
       'SHARC_Entry2_size':524212,
       'SHARC_LDR_201_descriptors_original':True,
       'SHARC_only_modified_record':177,
       'SHARC_PM_record_instructions':142,
       'M4_app_internal_CRC_valid':True,
       'Entry0_and_Entry2_archive_CRC_valid':True,
       'on_device_Line_6_Updater_executed':False,
       'flash_recovery_hardware_proven':False,
    }
if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
