import hashlib,json,struct
import pytest
import patch_amp as pa,hxf_ram as hr
from build_io_level_r08_pcm_observer import NAME,ROOT,R05,R05_SHA,FROZEN,FROZEN_SHA256,RX,REG
from io_level_r08_pcm_audit import decode,summarize,FIELDS
OUT=ROOT/'build/browser-ramrun'/NAME
HXF=OUT/(NAME+'.hxf')
sha=lambda x:hashlib.sha256(x).hexdigest()

def test_exact_frozen_sharc_m0_R05_comparator_and_RAM_plan():
    b=json.loads((OUT/'manifest-build.json').read_text());p=json.loads((OUT/'regions/plan.json').read_text());s=json.loads((OUT/'manifest-stage.json').read_text())
    assert sha(R05.read_bytes())==R05_SHA and sha(FROZEN.read_bytes())==FROZEN_SHA256
    assert sha(HXF.read_bytes())==b['HXF_SHA256']==s['HXF_SHA256']
    assert sha((OUT/'regions/plan.json').read_bytes())==s['plan_SHA256']
    a,_=pa.load_l6ia_from_any(str(FROZEN));r,_=pa.load_l6ia_from_any(str(R05));t,_=pa.load_l6ia_from_any(str(HXF))
    assert [i for i in range(15) if pa.get_entry_swapped(a,i)!=pa.get_entry_swapped(t,i)]==[0]
    rs,_=hr.app_segments(pa.get_entry_swapped(r,0));ts,_=hr.app_segments(pa.get_entry_swapped(t,0))
    assert [x[0] for x in rs]==[x[0] for x in ts]
    for (ad,ob),(_,nb) in zip(rs,ts):
        if ad==0x28d8fa80:
            assert len(nb)>len(ob)
            assert [i for i,(x,y) in enumerate(zip(ob,nb)) if x!=y and not (RX-ad<=i<RX-ad+4 or REG-ad<=i<REG-ad+4)]==[]
        else:assert ob==nb
    assert p['summary']['writes']=='ram' and p['summary']['overlay_sectors']==p['summary']['runs']==0
    assert p['summary']['changed']==[] and len(p['regions'])==9 and len(p['checks'])==2
    assert s['signature']=='IOR8' and s['command']==0x1d

def test_decoder_rejects_stale_revision_torn_and_impossible_amplitude():
    v=[0]*32;v[0]=0x38524f49;v[13]=40000;v[16]=800000
    assert decode(struct.pack('<32I',*v))['max_output']==800000
    for i,x in [(0,0),(1,1),(16,8388609)]:
        bad=v.copy();bad[i]=x
        with pytest.raises(ValueError):decode(struct.pack('<32I',*bad))
    with pytest.raises(ValueError):decode(b'')

def test_independent_PCM_cumulative_counts_detect_native_misses_and_coverage_gaps():
    def row(i,beat,frame,hot,db,skipped=0,seed=0):
        p=dict.fromkeys(FIELDS,0);p.update(frames=frame,boundary=frame*8+skipped,producer_words=frame*8+skipped+1,output_hot30=hot,output_hot40=hot,output_hot50=hot,skipped_words=skipped,seeds=seed,max_output=400000)
        return dict(time_s=i*.25,led_count=beat,output1_last=db,output_bar_pixels=114 if db>-30 else 25,pcm=p)
    rows=[row(0,0,0,0,-70),row(1,1,12000,0,-70),row(2,1,24000,100,-70),row(3,2,36000,100,-12),row(4,2,48000,200,-12),row(5,3,60000,200,-70)]
    x=summarize(rows);assert x['complete_tap_intervals']==2 and x['native_high_intervals']==1 and x['pcm_hot30_intervals']==2 and x['coverage_fraction']==1
    assert x['per_beat'][0]['pcm_hot30']==100 and not x['per_beat'][0]['native_detected']
