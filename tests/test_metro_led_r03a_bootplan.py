"""R03A actual exact donor HXF / unchanged LDR topology / RAM overlay gates.

No pedal I/O. Candidate is a SHARC-only boot isolation image, not the finished
audio/LED synchronization bridge. Avoid false-positive 'boot proven' claims.
"""
from pathlib import Path
import hashlib,json,struct,zlib
import pytest
import patch_amp as pa,l6ia,hxf_ram as hr
from metro_led_sharc_patch import parse_ldr
from build_metro_led_r03a_sharc_inplace import donor_patch,NAME
from metro_led_donor_patch import DONOR_MD5,DONOR_SHA256

ROOT=Path(__file__).resolve().parents[1]
DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
DEST=ROOT/'build/browser-ramrun'/NAME
HXF=DEST/(NAME+'.hxf')
PLAN=DEST/'regions/plan.json'

def pair():
    raw=DONOR.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==DONOR_SHA256
    assert hashlib.md5(raw).hexdigest()==DONOR_MD5
    original,yes=pa.load_l6ia_from_any(str(DONOR))
    assert yes
    newer,yes=pa.load_l6ia_from_any(str(HXF))
    assert yes
    return original,newer

def test_only_metronome_existing_142word_boot_record_changed_and_no_other_code():
    orig,new=pair()
    assert [i for i in range(15) if pa.get_entry_swapped(orig,i)!=pa.get_entry_swapped(new,i)]==[2]
    a,b=l6ia.parse(orig)[2],l6ia.parse(new)[2]
    assert a['payload_len']==b['payload_len']==524212
    assert a['payload_off']==b['payload_off']
    o=orig[a['payload_off']:a['payload_off']+a['payload_len']]
    n=new[b['payload_off']:b['payload_off']+b['payload_len']]
    orig_blocks,prefix,tail=parse_ldr(o)
    new_blocks,prefix1,tail1=parse_ldr(n)
    assert len(orig_blocks)==len(new_blocks)==201
    assert prefix==prefix1 and tail==tail1
    for k,(old,new_block) in enumerate(zip(orig_blocks,new_blocks)):
        assert old[:3]==new_block[:3]
        if k!=177:assert old==new_block
    assert orig_blocks[177][:3]==(5,142,0xe5386)
    generated,proof=donor_patch(orig)
    assert pa.get_entry_swapped(generated,2)==pa.get_entry_swapped(new,2)
    assert proof['LDR_topology_changed'] is False
    assert proof['M4_donor_unchanged'] is True

def test_metadata_header_crc_length_are_correct():
    _,new=pair()
    hdr=l6ia.swap32(l6ia.parse(new)[2]['sub'])
    assert len(hdr)==512
    m,v,crc,n=struct.unpack_from('<4I',hdr)
    assert m==0x56112603 and n==524212
    assert crc==zlib.crc32(hr.load(str(HXF))[2])

def test_ram_overlay_reconstructs_entire_entry2_eMMC_partition_including_metadata():
    orig,new=pair()
    plan=json.loads(PLAN.read_text())
    assert len(plan['regions'])==9
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['unit']=='HX Stomp'
    assert plan['summary']['overlay_sectors']==3
    assert plan['summary']['runs']==3
    assert plan['summary']['changed']==[[2,524212,524212,2]]
    assert plan['checks']==[[34819,1023,3485190247,2]]
    row=next(r for r in plan['regions'] if 'hook, overlay' in r['label'])
    raw=(PLAN.parent/row['file']).read_bytes()
    base=row['addr'];table=plan['summary']['table']
    n,=struct.unpack_from('<I',raw,table-base)
    assert n==3
    runs=[struct.unpack_from('<3I',raw,table-base+4+12*i) for i in range(n)]
    assert [k for k,_,_ in runs]==[0x8802,0x8803+1004,0x8803+1023]
    assert [count for _,count,_ in runs]==[1,1,1]
    a=l6ia.parse(orig)[2];b=l6ia.parse(new)[2]
    old_header=l6ia.swap32(a['sub']);new_header=l6ia.swap32(b['sub'])
    stock=hr.load(str(DONOR))[2];target=hr.load(str(HXF))[2]
    def sectors(hdr,data):
        return [hdr]+[data[512*i:512*(i+1)].ljust(512,b'\0') for i in range(1024)]
    source=sectors(old_header,stock)
    intended=sectors(new_header,target)
    actual=[]
    for k,original in enumerate(source):
        emmc=hr.PART_START[2]+k
        covering=[(s,c,ptr) for s,c,ptr in runs if s<=emmc<s+c]
        assert len(covering)<=1
        if covering:
            s,c,ptr=covering[0]
            offset=ptr-base+512*(emmc-s)
            actual.append(raw[offset:offset+512])
        else:actual.append(original)
    assert actual==intended
    assert [k for k,(a,b) in enumerate(zip(source,intended)) if a!=b]==[0,1005]

def test_webusb_page_and_sharc_only_manifest_enforce_correct_bootplan():
    from pathlib import Path
    m=json.loads((DEST/'manifest.json').read_text())
    assert m['status']=='STAGED_OFFLINE_ONLY_UNTESTED_ON_PHYSICAL_PEDAL'
    assert m['hxf_SHA256']==hashlib.sha256(HXF.read_bytes()).hexdigest()
    assert m['total_overlay_sectors']==3
    assert m['changed_SHARC_payload_sector_indices']==[1004]
    assert m['M4_donor_unchanged'] is True
    assert m['LDR_topology_changed'] is False
    assert m['ram_regions']==9
    assert m['hardware_run_started'] is False
    assert m['experimental_audio_sync_ready'] is False
    assert m['webusb_loader_sha256']==hashlib.sha256((DEST/'firmware-ramboot.dfu').read_bytes()).hexdigest()
    html=(DEST/'index.html').read_text()
    assert NAME in html
    assert "manifest.summary?.overlay_sectors!==3" in html
    assert "manifest.summary?.changed?.length!==1" in html
    assert "SHARC-only" in html
    assert "LED/audio synchronization" in html
    assert (DEST/'ramrun.js').read_bytes()==(ROOT/'web/experiments/metro-donor-v121-unchanged-control/ramrun.js').read_bytes()
