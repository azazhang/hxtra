"""R07 packed image and complete staged sector equivalence to pinned R05/R03C."""
import hashlib,json,struct,zlib
import pytest
import hxf_ram as hr,patch_amp as pa,l6ia
from metro_led_sharc_patch import parse_ldr,pm_words
from build_io_level_r07_native_peak_retention import NAME,ROOT,R05,R05_SHA,FROZEN,FROZEN_SHA256,ADDRESS,BLOCK,ORIGINAL,SRC
import sasm
OUT=ROOT/'build/browser-ramrun'/NAME
HXF=OUT/(NAME+'.hxf')
def sha(x):return hashlib.sha256(x).hexdigest()
@pytest.fixture(scope='module')
def archives():
    assert sha(R05.read_bytes())==R05_SHA and sha(FROZEN.read_bytes())==FROZEN_SHA256
    return tuple(pa.load_l6ia_from_any(str(x))[0] for x in (FROZEN,R05,HXF))
def raw2(a):
    e=l6ia.parse(a)[2];return a[e['payload_off']:e['payload_off']+e['payload_len']]
def test_exact_R05_M4_and_one_original_SHARC_LDR_record(archives):
    base,r05,r07=archives
    assert [i for i in range(15) if pa.get_entry_swapped(r05,i)!=pa.get_entry_swapped(r07,i)]==[2]
    assert [i for i in range(15) if pa.get_entry_swapped(base,i)!=pa.get_entry_swapped(r07,i)]==[0,2]
    old,op,ot=parse_ldr(raw2(r05));new,np,nt=parse_ldr(raw2(r07))
    assert len(old)==len(new)==201 and op==np and ot==nt
    assert all(a[:3]==b[:3] for a,b in zip(old,new))
    assert [i for i,(a,b) in enumerate(zip(old,new)) if a!=b]==[BLOCK]
    a,b=pm_words(old[BLOCK]),pm_words(new[BLOCK]);k=ADDRESS-old[BLOCK][2]
    assert a[k:k+7]==ORIGINAL
    c,_=sasm.assemble(SRC.read_text(),str(SRC))
    assert a[:k]==b[:k] and a[k+7:]==b[k+7:] and b[k:k+7]==c[0].words
    assert raw2(r05)[79*512:80*512]!=raw2(r07)[79*512:80*512]
    assert raw2(r05)[:79*512]==raw2(r07)[:79*512] and raw2(r05)[80*512:]==raw2(r07)[80*512:]
def test_actual_staged_RAM_overlay_and_header_crc(archives):
    base,_,r07=archives
    p=json.loads((OUT/'regions/plan.json').read_text());b=json.loads((OUT/'manifest-build.json').read_text());s=json.loads((OUT/'manifest-stage.json').read_text())
    assert sha(HXF.read_bytes())==b['HXF_SHA256']==s['HXF_SHA256']
    assert sha((OUT/'regions/plan.json').read_bytes())==s['plan_SHA256']
    assert p['summary']['writes']=='ram' and p['summary']['changed']==[[2,524212,524212,1]]
    assert p['summary']['overlay_sectors']==p['summary']['runs']==2 and len(p['regions'])==9
    oh=l6ia.swap32(l6ia.parse(base)[2]['sub']);nh=l6ia.swap32(l6ia.parse(r07)[2]['sub'])
    old,new=hr.load(str(FROZEN))[2],hr.load(str(HXF))[2]
    assert struct.unpack_from('<I',nh,8)[0]==zlib.crc32(new)
    assert p['checks']==[[0x8802,1,zlib.crc32(oh),2],[0x8803,1023,zlib.crc32(old[:1023*512]),2]]
    reg=next(x for x in p['regions'] if x['label'].startswith('hook, overlay table'));blob=(OUT/'regions'/reg['file']).read_bytes();addr=reg['addr'];off=p['summary']['table']-addr
    n,=struct.unpack_from('<I',blob,off);assert n==2
    rows=[struct.unpack_from('<3I',blob,off+4+12*i) for i in range(n)]
    assert [(a,n) for a,n,_ in rows]==[(0x8802,1),(0x8803+79,1)]
    for i in range(1025):
        a=0x8802+i;src=oh if i==0 else old[(i-1)*512:i*512];dst=nh if i==0 else new[(i-1)*512:i*512]
        match=[x for x in rows if x[0]<=a<x[0]+x[1]]
        actual=src if not match else blob[match[0][2]-addr+512*(a-match[0][0]):match[0][2]-addr+512*(a-match[0][0])+len(dst)]
        assert actual==dst
