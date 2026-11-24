#!/usr/bin/env python3
"""R08: M4 read-only observation of M0's existing I2S PCM ring. R05 comparator retained."""
from pathlib import Path
import hashlib,json,subprocess,sys,struct
import patch_amp as pa,patch_menu as pm,l6ia,setting_ids
from build_io_level_r07_native_peak_retention import R05,R05_SHA,FROZEN,FROZEN_SHA256,ROOT
NAME='IO-LEVEL-R08-DIRECT-PCM-RING-OBSERVER'
MOD='src/m4/io_level_r08_pcm_ring_observer.s'
RX=0x28da6134; REG=0x28d96adc
sha=lambda x:hashlib.sha256(x).hexdigest()
def patch(arch):
    read=lambda n:pa.get_entry_swapped(arch,n)
    old=read(0);p=pm.Patch(old,[],{},read)
    old_rx=p.u32(RX);r=p.read(REG,4);old_reg=setting_ids.bl_targets(struct.unpack('<2H',r),REG)[0]
    assert old_rx&1 and pm.bl(REG,old_reg)==r
    m=p.module(MOD);p.chain_ptr(RX,old_rx,before=m['pcm_ring_frame']);p.chain_bl(REG,old_reg,after=m['pcm_register']);p.finish_chains();repl=p.output();assert set(repl)=={0}
    new=repl[0];allowed=set(range(24))
    for site in (RX,REG):off=p.off(site,4);allowed.update(range(off,off+4))
    for s in p.segs:allowed.update(range(s[0],s[0]+20))
    assert not [i for i,(a,b) in enumerate(zip(old,new)) if a!=b and i<len(old)-8 and i not in allowed]
    out,_,_=l6ia.rebuild_archive(arch,repl)
    assert all(pa.get_entry_swapped(out,i)==read(i) for i in range(1,15))
    # All existing application segments other than appended M4 segment data / hook sites unchanged;
    # explicitly preserve M0 audio firmware byte for byte.
    import hxf_ram as hr
    ss,_=hr.app_segments(old);ds,_=hr.app_segments(new)
    assert next(b for a,b in ss if a==0x20000000)==next(b for a,b in ds if a==0x20000000)
    return out,{'R08_M0_segment_identical':True,'R08_SHARC_identical':True,'R08_R05_existing_Home_paint_unchanged':True,'R08_hook_sites':[hex(RX),hex(REG)],'R08_new_app_bytes':len(new)-len(old),'R08_symbols':{k:hex(m[k]) for k in ('pcm_ring_frame','pcm_command','pcm_stats','pcm_register')}}
def build():
    assert sha(FROZEN.read_bytes())==FROZEN_SHA256 and sha(R05.read_bytes())==R05_SHA
    a,h=pa.load_l6ia_from_any(str(R05));base,_=pa.load_l6ia_from_any(str(FROZEN));assert h
    assert [i for i in range(15) if pa.get_entry_swapped(a,i)!=pa.get_entry_swapped(base,i)]==[0]
    out,meta=patch(a);target=ROOT/'build/browser-ramrun'/NAME;target.mkdir(parents=True,exist_ok=True)
    l=target/(NAME+'.l6ia');f=target/(NAME+'.hxf');l.write_bytes(out)
    subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(l)],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(l),str(f),'--donor',str(FROZEN)],check=True,stdout=subprocess.DEVNULL)
    x,was=pa.load_l6ia_from_any(str(f));assert was and x==out
    meta.update(variant=NAME,HXF_SHA256=sha(f.read_bytes()),donor_R03C_SHA256=FROZEN_SHA256,exact_R05_SHA256=R05_SHA,modified_archive_entries=[0],original_14_non_M4_entries_identical=True,read_only_PCM_observer=True,hardware_tested=False,ram_only=True)
    (target/'manifest-build.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
if __name__=='__main__':build()
