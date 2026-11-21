"""R03C exact donor / boot-record topology / sector-by-sector RAM overlay QA."""
from pathlib import Path
import hashlib,json,struct,zlib
import pytest
import patch_amp as pa,l6ia,hxf_ram as hr
from metro_led_sharc_patch import parse_ldr
from build_metro_led_r03c import NAME,DONOR_SHA256,patch_m4,patch_sharc
from metro_led_r03c_probe import decode,DATA_BYTES
from test_metro_led_r03c_tap_grace import m4
from test_metro_led_r03b_transport import BMachine

ROOT=Path(__file__).parents[1]
DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
DIR=ROOT/'build/browser-ramrun'/NAME
HXF=DIR/(NAME+'.hxf')
PLAN=DIR/'regions/plan.json'

@pytest.fixture(scope='module')
def pair():
    assert hashlib.sha256(DONOR.read_bytes()).hexdigest()==DONOR_SHA256
    donor,yes=pa.load_l6ia_from_any(str(DONOR));assert yes
    candidate,yes=pa.load_l6ia_from_any(str(HXF));assert yes
    return donor,candidate

def test_only_four_original_M4_sites_and_one_original_SHARC_record_changed(pair):
    donor,candidate=pair
    assert [i for i in range(15) if pa.get_entry_swapped(donor,i)!=pa.get_entry_swapped(candidate,i)]==[0,2]
    m4patched,im=patch_m4(donor)
    assert im['M4_disallowed_donor_byte_mutations']==0
    assert im['M4_changed_hook_sites']==['0x28d98f78','0x28e045a0','0x28d96adc','0x28da6138']
    assert pa.get_entry_swapped(m4patched,0)==pa.get_entry_swapped(candidate,0)
    sharcpatched,ish=patch_sharc(m4patched)
    assert pa.get_entry_swapped(sharcpatched,2)==pa.get_entry_swapped(candidate,2)
    old,new=l6ia.parse(donor)[2],l6ia.parse(candidate)[2]
    assert old['payload_len']==new['payload_len']==524212
    ob,op,ot=parse_ldr(donor[old['payload_off']:old['payload_off']+524212])
    nb,np,nt=parse_ldr(candidate[new['payload_off']:new['payload_off']+524212])
    assert len(ob)==len(nb)==201
    assert op==np and ot==nt
    assert [i for i,(a,b) in enumerate(zip(ob,nb)) if a!=b]==[177]
    assert ob[177][:3]==nb[177][:3]==(5,142,0xe5386)
    assert all(a[:3]==b[:3] for a,b in zip(ob,nb))
    original_m4=pa.get_entry_swapped(donor,0)
    updated_m4=pa.get_entry_swapped(candidate,0)
    for feature in (b'DSP Usage Display',b'Breathing Line',b'Main+Snd',b'Path A',b'FS1 Hold'):
        assert feature in original_m4 and feature in updated_m4
    for i in range(15):
        if i not in (0,2):
            assert pa.get_entry_swapped(donor,i)==pa.get_entry_swapped(candidate,i)

def test_header_and_full_1025_sector_RAM_overlay_exactly_matches_candidate(pair):
    donor,candidate=pair
    old,new=l6ia.parse(donor)[2],l6ia.parse(candidate)[2]
    old_hdr=l6ia.swap32(old['sub'])
    new_hdr=l6ia.swap32(new['sub'])
    assert struct.unpack_from('<I',new_hdr,12)[0]==524212
    assert struct.unpack_from('<I',new_hdr,8)[0]==zlib.crc32(hr.load(str(HXF))[2])
    plan=json.loads(PLAN.read_text())
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['changed']==[[2,524212,524212,3]]
    assert plan['summary']['overlay_sectors']==4
    assert plan['summary']['runs']==3
    assert len(plan['regions'])==9
    assert plan['checks']==[[34819,1023,3485190247,2]]
    item=next(r for r in plan['regions'] if 'hook, overlay' in r['label'])
    payload=(PLAN.parent/item['file']).read_bytes()
    addr=item['addr']
    count,=struct.unpack_from('<I',payload,plan['summary']['table']-addr)
    assert count==3
    runs=[struct.unpack_from('<3I',payload,plan['summary']['table']-addr+4+12*i) for i in range(3)]
    assert [r[0] for r in runs]==[0x8802,0x8803+1004,0x8803+1023]
    assert [r[1] for r in runs]==[1,2,1]
    orig=hr.load(str(DONOR))[2]
    dst=hr.load(str(HXF))[2]
    old_full=[old_hdr]+[orig[i*512:(i+1)*512].ljust(512,b'\0') for i in range(1024)]
    new_full=[new_hdr]+[dst[i*512:(i+1)*512].ljust(512,b'\0') for i in range(1024)]
    reconstructed=[]
    for i,old_sector in enumerate(old_full):
        emmc_sector=0x8802+i
        match=[r for r in runs if r[0]<=emmc_sector<r[0]+r[1]]
        assert len(match)<=1
        if not match:
            reconstructed.append(old_sector)
        else:
            start,n,pointer=match[0]
            offset=pointer-addr+512*(emmc_sector-start)
            reconstructed.append(payload[offset:offset+512])
    assert reconstructed==new_full
    assert [i for i,(a,b) in enumerate(zip(old_full,new_full)) if a!=b]==[0,1005,1006]

def test_exact_extended_84byte_readonly_M4_diagnostic_and_timing(m4):
    m=BMachine(m4);m.prepare()
    m.emit(1,us=1000000)
    m.time_us=1000423
    m.stamp()
    m.call('mp_register')
    assert m.registered[0]==0x50
    req=0x20001000
    m.uc.mem_write(req+0xc,struct.pack('<H',0x1234))
    m.call('mp_command',r0=0x20004000,r1=req)
    assert m.sent[:3]==(0x20004000,0x1234,0)
    assert m.sent[3][:2]==bytes((0xc4,DATA_BYTES))
    r=decode(m.sent[3][2:])
    assert r['revision']==NAME
    assert r['last_M4_LED_request_to_first_SPI_TX_us']==423
    assert r['last_accepted_M4_LED_on_timestamp_us_u32']==1000000
    assert r['last_event_reaching_M4_SPI_tx_count']==0x80000001
    assert r['last_M4_TX_pair_is_valid']
    assert r['M4_latency_measure_valid']
    assert not r['SHARC_consumer_counter_measured']
    assert not r['actual_optical_LED_to_acoustic_click_ms_measured']
    bad=bytearray(m.sent[3][2:])
    struct.pack_into('<I',bad,44,0)
    with pytest.raises(ValueError,match='wrong firmware revision'):decode(bytes(bad))

def test_staged_page_protects_identity_RAM_only_and_explicitly_discloses_lag(pair):
    m=json.loads((DIR/'manifest.json').read_text())
    assert m['variant']==NAME
    assert m['stage']=='STAGEQA00_OFFLINE_HW_UNTESTED'
    assert m['hardware_run_initiated'] is False
    assert m['physical_double_click_fix_verified'] is False
    assert m['perceptible_LED_to_audio_delay_fixed'] is False
    assert m['RAM_only'] is True
    assert m['hxf_sha256']==hashlib.sha256(HXF.read_bytes()).hexdigest()
    assert m['ram_plan_sha256']==hashlib.sha256(PLAN.read_bytes()).hexdigest()
    assert m['webusb_loader_sha256']==hashlib.sha256((DIR/'firmware-ramboot.dfu').read_bytes()).hexdigest()
    assert m['webusb_script_sha256']==hashlib.sha256((DIR/'ramrun.js').read_bytes()).hexdigest()
    assert m['page_sha256']==hashlib.sha256((DIR/'index.html').read_bytes()).hexdigest()
    assert (DIR/'ramrun.js').read_bytes()==(ROOT/'web/experiments/metro-donor-v121-unchanged-control/ramrun.js').read_bytes()
    html=(DIR/'index.html').read_text()
    assert NAME in html
    assert 'manifest.summary?.overlay_sectors!==4' in html
    assert 'manifest.summary?.changed?.[0]?.[3]!==3' in html
    assert 'The perceptible LED-to-audio delay has NOT been resolved' in html
    assert '4,600 SPI frames' in html
