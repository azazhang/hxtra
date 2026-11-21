"""R02D donor-preserving boot image and metadata integrity regressions.

Distinguishes prior HWFAIL02 from a patch that never increases SHARC partition
length and overlays the changed header sector at 0x8802 in RAM.
"""
from pathlib import Path
import json,hashlib,struct,zlib
import pytest
import patch_amp as pa,l6ia,hxf_ram as hr
from metro_led_r02d_sharc_preserve_size import sharc_preserve_size
from metro_led_r02d_ramplan_header import make_plan
from metro_led_donor_patch import DONOR_SHA256

ROOT=Path(__file__).resolve().parents[1]
DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
HXF=ROOT/'build/startup-isolation/METRO-LEDSYNC-R02D-SHARC-SIZE-PRESERVED.hxf'
PLAN=ROOT/'build/startup-isolation/METRO-LEDSYNC-R02D-HEADER-OVERLAY/regions/plan.json'

def donor_and_candidate():
    if not HXF.exists():pytest.skip('R02D offline HXF missing')
    orig,_=pa.load_l6ia_from_any(str(DONOR));new,_=pa.load_l6ia_from_any(str(HXF))
    assert hashlib.sha256(DONOR.read_bytes()).hexdigest()==DONOR_SHA256
    return orig,new

def test_sharc_entry_has_exact_original_donor_length_and_other_entries_untouched():
    orig,new=donor_and_candidate()
    a=l6ia.parse(orig);b=l6ia.parse(new)
    assert a[2]['payload_len']==b[2]['payload_len']==524212
    assert sum(pa.get_entry_swapped(orig,i)!=pa.get_entry_swapped(new,i) for i in range(15))==1
    for i in range(15):
        if i!=2:assert pa.get_entry_swapped(orig,i)==pa.get_entry_swapped(new,i)

def test_direct_sharc_transform_reproducibly_preserves_all_dm_and_all_other_pm():
    orig,new=donor_and_candidate()
    generated,report=sharc_preserve_size(orig)
    assert pa.get_entry_swapped(generated,2)==pa.get_entry_swapped(new,2)
    assert report['entry2_size_delta']==0
    assert report['saved_ldr_header_bytes']==84
    assert report['initialized_DM_words_unchanged']==22468
    assert report['initialized_PM_addresses_changed_exactly']==15

def test_entry2_header_in_hxf_matches_new_payload_crc_and_length():
    _,new=donor_and_candidate()
    e=l6ia.parse(new)[2]
    marker,flags,crc,plen=struct.unpack_from('>4I',e['sub'])
    assert marker==0x56112603 and plen==524212
    assert crc==zlib.crc32(hr.load(str(HXF))[2])

def test_runtime_ram_overlay_contains_correct_modified_header_sector():
    orig,new=donor_and_candidate()
    if not PLAN.exists():pytest.skip('R02D header overlay plan missing')
    plan=json.loads(PLAN.read_text())
    assert plan['summary']['writes']=='ram'
    assert len(plan['regions'])==9
    assert plan['summary']['overlay_sectors']==20
    assert plan['summary']['runs']==3
    expected=l6ia.swap32(l6ia.parse(new)[2]['sub'])
    assert expected!=l6ia.swap32(l6ia.parse(orig)[2]['sub'])
    row=next(r for r in plan['regions'] if 'hook, overlay' in r['label'])
    raw=(PLAN.parent/row['file']).read_bytes()
    origin=row['addr'];base=plan['summary']['table'];nruns=struct.unpack_from('<I',raw,base-origin)[0]
    matches=[]
    for i in range(nruns):
        sector,count,data=struct.unpack_from('<3I',raw,base-origin+4+12*i)
        if sector<=hr.PART_START[2]<sector+count:
            pos=data-origin+512*(hr.PART_START[2]-sector)
            matches.append(raw[pos:pos+512])
    assert matches==[expected]
    assert plan['checks']==[[34819,1023,3485190247,2]]

def test_HXTRA_DSP_meter_display_and_827_browser_names_unchanged():
    orig,new=donor_and_candidate()
    e0=pa.get_entry_swapped(orig,0);new_e0=pa.get_entry_swapped(new,0)
    assert e0==new_e0
    for label in (b'DSP Usage Display',b'Breathing Line',b'Main+Snd',b'Tap LED'):
        assert label in new_e0


def test_actual_ram_hook_overlay_reconstructs_all_1024_sharc_partition_sectors():
    """Exercise overlay_find's sorted run table using its saved runtime bytes.

    This tests every sector the device's M4 boot code could read, including
    sector 0x8802's new size/CRC metadata and the final payload sector. The
    prior HWFAIL02 plan did NOT update this header, leaving a length overrun.
    """
    orig,new=donor_and_candidate()
    plan=json.loads(PLAN.read_text())
    erow=next(r for r in plan['regions'] if 'hook, overlay' in r['label'])
    blob=(PLAN.parent/erow['file']).read_bytes()
    mem0=erow['addr']; table=plan['summary']['table']
    nrun=struct.unpack_from('<I',blob,table-mem0)[0]
    runs=[struct.unpack_from('<3I',blob,table-mem0+4+12*k) for k in range(nrun)]
    assert nrun==3
    assert all(a[0]+a[1]<=b[0] for a,b in zip(runs,runs[1:]))
    old_sector=l6ia.swap32(l6ia.parse(orig)[2]['sub'])
    new_sector=l6ia.swap32(l6ia.parse(new)[2]['sub'])
    orig_payload=hr.load(str(DONOR))[2]
    new_payload=hr.load(str(HXF))[2]
    original=[old_sector]+[orig_payload[j:j+512].ljust(512,b'\0') for j in range(0,524288,512)]
    candidate=[new_sector]+[new_payload[j:j+512].ljust(512,b'\0') for j in range(0,524288,512)]
    assert len(original)==len(candidate)==1025
    first=hr.PART_START[2]
    actual=[]
    for i,prev in enumerate(original):
        sector=first+i
        matched=[(start,count,memory) for start,count,memory in runs if start<=sector<start+count]
        assert len(matched)<=1
        if matched:
            start,count,mem=matched[0]
            off=mem-mem0+512*(sector-start)
            loaded=blob[off:off+512]
            assert len(loaded)==512
            actual.append(loaded)
        else:actual.append(prev)
    assert actual==candidate, [i for i,(a,b) in enumerate(zip(actual,candidate)) if a!=b][:25]
    assert original[0]!=candidate[0]
    assert candidate[0][12:16]==struct.pack('<I',524212)
