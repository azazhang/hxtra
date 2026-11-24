#!/usr/bin/env python3
"""R11 RAM-only overlay, verified against all 1025 Entry2 sectors."""
import hashlib,json,struct,zlib
from pathlib import Path
import hxf_ram as hr,patch_amp as pa,l6ia
from build_io_level_r11_uniform_scale import NAME,FROZEN,FROZEN_SHA256,R05,R05_SHA,ROOT,R10,R10_SHA

def sha(x):return hashlib.sha256(x).hexdigest()

def plan():
    assert sha(FROZEN.read_bytes())==FROZEN_SHA256 and sha(R05.read_bytes())==R05_SHA
    out=ROOT/'build/browser-ramrun'/NAME
    hxf=out/(NAME+'.hxf')
    report=json.loads((out/'manifest-build.json').read_text())
    assert sha(hxf.read_bytes())==report['HXF_SHA256']
    stock=hr.load(str(FROZEN),stock=True);new=hr.load(str(hxf))
    n=struct.unpack_from('<I',stock[0],4)[0];crc=zlib.crc32(stock[0][0x34:n]);assert crc==0x5ed9d947
    ref=hr.APPS[0x2b81e740];_,funcs,card=ref
    segs,_=hr.app_segments(stock[0])
    for fn,lit in funcs.values():
        assert hr.seg_read(segs,fn,len(hr.PROLOGUE))==hr.PROLOGUE
        assert struct.unpack('<I',hr.seg_read(segs,lit,4))[0]==card
    hr.APPS[crc]=ref
    old_a,_=pa.load_l6ia_from_any(str(FROZEN));new_a,_=pa.load_l6ia_from_any(str(hxf));r05,_=pa.load_l6ia_from_any(str(R05))
    assert pa.get_entry_swapped(new_a,0)!=pa.get_entry_swapped(r05,0)
    assert report["M0_segment_identical"] and report["R03C_GR_Home_preserved"]
    assert sha(R10.read_bytes())==R10_SHA
    r10,_=pa.load_l6ia_from_any(str(R10))
    assert all(pa.get_entry_swapped(r10,i)==pa.get_entry_swapped(new_a,i) for i in range(1,15))
    assert [i for i in range(15) if pa.get_entry_swapped(old_a,i)!=pa.get_entry_swapped(new_a,i)]==[0,2]
    oh=l6ia.swap32(l6ia.parse(old_a)[2]['sub']);nh=l6ia.swap32(l6ia.parse(new_a)[2]['sub'])
    assert len(oh)==len(nh)==512 and oh!=nh
    assert struct.unpack_from('<I',nh,12)[0]==len(new[2])==len(stock[2])==524212
    assert struct.unpack_from('<I',nh,8)[0]==zlib.crc32(new[2])
    # Override solely to include correct SHARC header and avoid an unnecessary
    # overlay of identical last partial sector. The original padded bytes on
    # the card need no change; compare only defined payload bytes.
    real_overlay=hr.overlay
    def overlay(a,b):
        sectors,notes=real_overlay(a,b)
        assert [x[0] for x in notes]==[2]
        actual=[(hr.PAYLOAD[2]+k//512,b[2][k:k+512].ljust(512,b'\0')) for k in range(0,len(b[2]),512) if a[2][k:k+512]!=b[2][k:k+512]]
        assert [s-hr.PAYLOAD[2] for s,_ in actual]==report['actual_changed_payload_sectors']
        assert all(s<hr.PAYLOAD[2]+1023 for s,_ in actual)
        return [(hr.PART_START[2],nh)]+actual,[(2,len(a[2]),len(b[2]),len(actual))]
    hr.overlay=overlay
    try:regions,checks,summary=hr.plan(str(hxf),str(FROZEN),writes='ram')
    finally:hr.overlay=real_overlay
    assert summary['unit']=='HX Stomp' and summary['writes']=='ram' and len(regions)==9
    assert summary['overlay_sectors']==1+len(report['actual_changed_payload_sectors'])
    assert checks==[(hr.PAYLOAD[2],1023,zlib.crc32(stock[2][:1023*512]),2)]
    checks.insert(0,(hr.PART_START[2],1,zlib.crc32(oh),2))
    addr,blob=next((ad,b) for ad,b,l in regions if l.startswith('hook, overlay table'))
    pos=summary['table']-addr;num,=struct.unpack_from('<I',blob,pos)
    runs=[struct.unpack_from('<3I',blob,pos+4+12*i) for i in range(num)]
    assert num==summary['runs']
    assert sum(n for _,n,_ in runs)==summary['overlay_sectors']
    original=[oh]+[stock[2][k:k+512].ljust(512,b'\0') for k in range(0,len(stock[2]),512)]
    expected=[nh]+[new[2][k:k+512].ljust(512,b'\0') for k in range(0,len(new[2]),512)]
    rebuilt=[]
    for i,b in enumerate(original):
        s=hr.PART_START[2]+i; matches=[(a,n,p) for a,n,p in runs if a<=s<a+n];assert len(matches)<=1
        if matches:
            a,n,p=matches[0];k=p-addr+512*(s-a);rebuilt.append(blob[k:k+512])
        else:rebuilt.append(b)
    assert rebuilt==expected and len(rebuilt)==1025
    target=out/'regions';target.mkdir(parents=True,exist_ok=True)
    result={'regions':[],'checks':checks,'summary':summary}
    for i,(a,b,l) in enumerate(regions):
        f=f'{i:02d}_{a:08x}.bin';(target/f).write_bytes(b);result['regions'].append({'addr':a,'file':f,'label':l})
    (target/'plan.json').write_text(json.dumps(result,indent=1)+'\n')
    p={'variant':NAME,'ram_only':True,'hardware_tested':False,'donor_R03C_SHA256':FROZEN_SHA256,'candidate_SHA256':report['HXF_SHA256'],'plan_SHA256':sha((target/'plan.json').read_bytes()),'checks':checks,'summary':summary,'verified_all_1025_sectors':True,'R05_native_ledger_preserved':True,'SHARC_header_CRC32':hex(zlib.crc32(new[2]))}
    (out/'manifest-plan.json').write_text(json.dumps(p,indent=2)+'\n');print(json.dumps(p,indent=2))
if __name__=='__main__':plan()
