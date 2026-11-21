"""R03B immutable donor / same-shape SHARC / real RAM overlay / USB diagnostic QA."""
from pathlib import Path
import hashlib,json,struct,zlib
import pytest
import patch_amp as pa,l6ia,hxf_ram as hr
from metro_led_sharc_patch import parse_ldr
from build_metro_led_r03b import NAME,DONOR_SHA256,patch_m4,patch_sharc
from metro_led_r03b_probe import decode,SIGNATURE
from test_metro_led_r03b_transport import BMachine,m4

ROOT=Path(__file__).parents[1]
DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
DIR=ROOT/'build/browser-ramrun'/NAME
HXF=DIR/(NAME+'.hxf')
PLAN=DIR/'regions/plan.json'

@pytest.fixture(scope='module')
def pair():
    assert hashlib.sha256(DONOR.read_bytes()).hexdigest()==DONOR_SHA256
    donor,_=pa.load_l6ia_from_any(str(DONOR))
    candidate,_=pa.load_l6ia_from_any(str(HXF))
    return donor,candidate

def test_exact_donor_appended_M4_4_hooks_and_only_original_sharc_metronome_record(pair):
    donor,candidate=pair
    changed=[i for i in range(15) if pa.get_entry_swapped(donor,i)!=pa.get_entry_swapped(candidate,i)]
    assert changed==[0,2]
    expected_m4,_=patch_m4(donor)
    assert pa.get_entry_swapped(expected_m4,0)==pa.get_entry_swapped(candidate,0)
    expected_sharc,_=patch_sharc(expected_m4)
    assert pa.get_entry_swapped(expected_sharc,2)==pa.get_entry_swapped(candidate,2)
    original,updated=l6ia.parse(donor)[2],l6ia.parse(candidate)[2]
    assert original['payload_len']==updated['payload_len']==524212
    old_blocks,old_pre,old_tail=parse_ldr(donor[original['payload_off']:original['payload_off']+524212])
    new_blocks,new_pre,new_tail=parse_ldr(candidate[updated['payload_off']:updated['payload_off']+524212])
    assert len(old_blocks)==len(new_blocks)==201
    assert old_pre==new_pre and old_tail==new_tail
    assert [i for i,(a,b) in enumerate(zip(old_blocks,new_blocks)) if a!=b]==[177]
    assert all(a[:3]==b[:3] for a,b in zip(old_blocks,new_blocks))
    assert old_blocks[177][:3]==new_blocks[177][:3]==(5,142,0xe5386)
    for i in range(15):
        if i not in (0,2):
            assert pa.get_entry_swapped(donor,i)==pa.get_entry_swapped(candidate,i)

def test_correct_crc32_header_and_four_sector_ram_overlay_reconstruct_all_1025_sectors(pair):
    donor,candidate=pair
    old,new=l6ia.parse(donor)[2],l6ia.parse(candidate)[2]
    orig_hdr=l6ia.swap32(old['sub'])
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
    packet=next(r for r in plan['regions'] if 'hook, overlay' in r['label'])
    buffer=(PLAN.parent/packet['file']).read_bytes()
    start=packet['addr'];table=plan['summary']['table']
    count,=struct.unpack_from('<I',buffer,table-start)
    assert count==3
    runs=[struct.unpack_from('<3I',buffer,table-start+4+12*k) for k in range(count)]
    assert [r[0] for r in runs]==[0x8802,0x8803+1004,0x8803+1023]
    assert [r[1] for r in runs]==[1,2,1]
    old_payload=hr.load(str(DONOR))[2]
    new_payload=hr.load(str(HXF))[2]
    original=[orig_hdr]+[old_payload[k*512:(k+1)*512].ljust(512,b'\0') for k in range(1024)]
    wanted=[new_hdr]+[new_payload[k*512:(k+1)*512].ljust(512,b'\0') for k in range(1024)]
    actual=[]
    for i,byteblock in enumerate(original):
        sector=0x8802+i
        match=[r for r in runs if r[0]<=sector<r[0]+r[1]]
        assert len(match)<=1
        if match:
            l,c,addr=match[0]
            actual.append(buffer[addr-start+512*(sector-l):addr-start+512*(sector-l+1)])
        else:actual.append(byteblock)
    assert actual==wanted
    assert [k for k,(a,b) in enumerate(zip(original,wanted)) if a!=b]==[0,1005,1006]

def test_R03B_diag_uses_read_only_0x50_and_rejects_wrong_firmware_signature(m4):
    m=BMachine(m4)
    m.prepare()
    m.call('mp_register')
    assert m.registered[0]==0x50
    request=0x20001000
    m.uc.mem_write(request+0xc,struct.pack('<H',0x1234))
    m.call('mp_command',r0=0x20004000,r1=request)
    assert m.sent[:3]==(0x20004000,0x1234,0)
    assert m.sent[3][:2]==b'\xc4\x30'
    row=decode(m.sent[3][2:])
    assert row['revision']==NAME
    assert row['raw_LED_event_count']==0
    assert row['SPI_tx_frames_stamped']==0
    assert not row['last_M4_TX_pair_is_valid']
    bad=bytearray(m.sent[3][2:])
    struct.pack_into('<I',bad,44,0)
    with pytest.raises(ValueError,match='wrong diagnostic revision'):decode(bytes(bad))

def test_staged_page_exact_identity_ram_only_no_physical_boot_claim(pair):
    m=json.loads((DIR/'manifest.json').read_text())
    assert m['variant']==NAME
    assert m['stage']=='STAGEQA00_OFFLINE_NOT_HARDWARE_TESTED'
    assert m['hardware_run_initiated'] is False
    assert m['physical_boot_verified'] is False
    assert m['physical_LED_audio_sync_verified'] is False
    assert m['ram_only'] is True
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
    assert '20ms' in html
    assert 'never been run together on hardware' in html
