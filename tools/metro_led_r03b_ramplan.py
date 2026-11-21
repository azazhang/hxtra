#!/usr/bin/env python3
"""R03B RAM-only overlay with *both* revised M4 application and SHARC Entry2.

We copy only the existing exact HXtra donor M4 application, change its four
audited hooks, then redirect eMMC reads of the revised SHARC PM sector and
the correct SHARC metadata header 0x8802 from RAM. No eMMC write is permitted.
"""
from pathlib import Path
import hashlib,struct,json,zlib
import hxf_ram as hr,patch_amp as pa,l6ia
from metro_led_r02c_ramplan import DONOR_APP_CRC,STOCK_APP_CRC,DONOR_MD5
from metro_led_donor_patch import DONOR_SHA256
from build_metro_led_r03b import NAME
ROOT=Path(__file__).resolve().parents[1]

def plan(donor:Path,hxf:Path,out:Path):
    raw=donor.read_bytes()
    assert hashlib.md5(raw).hexdigest()==DONOR_MD5
    assert hashlib.sha256(raw).hexdigest()==DONOR_SHA256
    stock=hr.load(str(donor),stock=True)
    valid_len=struct.unpack_from('<I',stock[0],4)[0]
    assert zlib.crc32(stock[0][0x34:valid_len])==DONOR_APP_CRC
    reference=hr.APPS[STOCK_APP_CRC]
    _,funcs,card=reference
    segs,_=hr.app_segments(stock[0])
    for fname,(fn,lit) in funcs.items():
        assert hr.seg_read(segs,fn,len(hr.PROLOGUE))==hr.PROLOGUE
        assert struct.unpack('<I',hr.seg_read(segs,lit,4))[0]==card
    hr.APPS[DONOR_APP_CRC]=reference
    old,_=pa.load_l6ia_from_any(str(donor))
    new,_=pa.load_l6ia_from_any(str(hxf))
    assert len(l6ia.parse(old))==len(l6ia.parse(new))==15
    altered=[i for i in range(15) if pa.get_entry_swapped(old,i)!=pa.get_entry_swapped(new,i)]
    assert altered==[0,2],altered
    a=l6ia.parse(old)[2]
    b=l6ia.parse(new)[2]
    assert a['payload_len']==b['payload_len']==524212
    old_header=l6ia.swap32(a['sub'])
    new_header=l6ia.swap32(b['sub'])
    assert len(old_header)==len(new_header)==512
    assert old_header!=new_header
    magic,version,crc,plen=struct.unpack_from('<4I',new_header)
    assert magic==0x56112603 and plen==524212
    assert crc==zlib.crc32(hr.load(str(hxf))[2])
    base_overlay=hr.overlay
    def with_header(stock,new):
        sectors,notes=base_overlay(stock,new)
        assert [x[0] for x in notes]==[2]
        assert notes[0][1:3]==(524212,524212)
        assert all(s!=hr.PART_START[2] for s,_ in sectors)
        return [(hr.PART_START[2],new_header)]+sectors,notes
    hr.overlay=with_header
    try:regions,checks,summary=hr.plan(str(hxf),str(donor),writes='ram')
    finally:hr.overlay=base_overlay
    assert summary['unit']=='HX Stomp'
    assert summary['writes']=='ram'
    assert summary['overlay_sectors']==4
    assert summary['runs']==3
    assert len(regions)==9 and len(checks)==1
    assert checks==[(34819,1023,3485190247,2)]
    # Read the exact run table the actual RAM hook will use.
    hook=[(ad,b) for ad,b,label in regions if label.startswith('hook, overlay table')]
    assert len(hook)==1
    addr,blob=hook[0]
    pos=summary['table']-addr
    nrun,=struct.unpack_from('<I',blob,pos)
    assert nrun==3
    runs=[struct.unpack_from('<3I',blob,pos+4+12*i) for i in range(nrun)]
    assert [x[0] for x in runs]==[hr.PART_START[2],hr.PAYLOAD[2]+1004,hr.PAYLOAD[2]+1023]
    assert [x[1] for x in runs]==[1,2,1]
    old_payload=stock[2]
    new_payload=hr.load(str(hxf))[2]
    source=[old_header]+[old_payload[k*512:(k+1)*512].ljust(512,b'\0') for k in range(1024)]
    desired=[new_header]+[new_payload[k*512:(k+1)*512].ljust(512,b'\0') for k in range(1024)]
    from_overlay=[]
    for i,sector in enumerate(source):
        s=hr.PART_START[2]+i
        match=[(start,count,where) for start,count,where in runs if start<=s<start+count]
        assert len(match)<=1
        if match:
            st,n,d=match[0]
            off=d-addr+512*(s-st)
            from_overlay.append(blob[off:off+512])
        else:from_overlay.append(sector)
    assert from_overlay==desired
    assert [i for i,(x,y) in enumerate(zip(source,desired)) if x!=y]==[0,1005,1006]
    out.mkdir(parents=True,exist_ok=True)
    output={'regions':[],'checks':checks,'summary':summary}
    for i,(address,data,label) in enumerate(regions):
        name=f'{i:02d}_{address:08x}.bin'
        (out/name).write_bytes(data)
        output['regions'].append({'addr':address,'file':name,'label':label})
    (out/'plan.json').write_text(json.dumps(output,indent=1))
    report={
      'variant':NAME,
      'hardware_tested':False,
      'ram_only':True,
      'writes':summary['writes'],
      'donor_hxf_sha256':DONOR_SHA256,
      'candidate_hxf_sha256':hashlib.sha256(hxf.read_bytes()).hexdigest(),
      'm4_changed_exact_donor':True,
      'sharc_only_original_record_177_changed':True,
      'sharc_original_entry2_bytes':524212,
      'sharc_new_entry2_bytes':524212,
      'original_201_LDR_descriptors_preserved':True,
      'header_overlay_emmc_sector':hex(hr.PART_START[2]),
      'header_crc32_original':hex(struct.unpack_from('<I',old_header,8)[0]),
      'header_crc32_candidate':hex(crc),
      'genuinely_changed_sharc_payload_sectors':[1004,1005],
      'padded_trailing_partial_sector':1023,
      'overlaid_sectors':summary['overlay_sectors'],
      'overlay_runs':summary['runs'],
      'ram_regions':len(regions),
      'checks':checks,
      'plan_sha256':hashlib.sha256((out/'plan.json').read_bytes()).hexdigest(),
    }
    (out.parent/'manifest-plan.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    home=ROOT/'build/browser-ramrun'/NAME
    d=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
    h=home/(NAME+'.hxf')
    print(json.dumps(plan(d,h,home/'regions'),indent=2))
if __name__=='__main__':main()
