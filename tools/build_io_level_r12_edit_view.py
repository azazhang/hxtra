#!/usr/bin/env python3
"""R12: exact R11 plus Edit view paint subscribers; retain all old callback chains."""
import json,subprocess,sys,struct,zlib
import m4asm,patch_amp as pa,patch_menu as pm,l6ia
from build_io_level_r09_direct_meter import ROOT,FROZEN,FROZEN_SHA256,R05,R05_SHA,sha
NAME='IO-LEVEL-R12-EDIT-VIEW-PEAK-METERS'
R11_NAME='IO-LEVEL-R11-UNIFORM-5DB-PEAK-METERS'
R11=ROOT/'build/browser-ramrun'/R11_NAME/(R11_NAME+'.hxf')
R11_SHA='fccda1d30e7f7ef5256ea00985d513fda04b21b551e97e1d110d448d26b86bce'
BASE=0x28e62324
def build():
    assert sha(R11.read_bytes())==R11_SHA and sha(FROZEN.read_bytes())==FROZEN_SHA256
    arch,h=pa.load_l6ia_from_any(str(R11));assert h
    donor,h=pa.load_l6ia_from_any(str(FROZEN));assert h
    old=pa.get_entry_swapped(arch,0)
    p=pm.Patch(old,[],{},lambda i:pa.get_entry_swapped(arch,i))
    # Verify exact R11 module and existing frozen callback chains, including DSP Usage.
    a,sa=m4asm.assemble_module(str(ROOT/'src/m4/io_level_r11_direct_meter.s'))
    assert p.read(BASE,len(a))==a and BASE+sa['r09_stats']==0x28e626f0
    orig={0x28d96da0:0x28e55401,0x28d96e38:0x28e554ad}
    frozen=pm.Patch(pa.get_entry_swapped(donor,0),[],{},lambda i:pa.get_entry_swapped(donor,i))
    for site,target in orig.items():
        assert p.u32(site)==target==frozen.u32(site)
    assert p.read(0x28e55400,44)==frozen.read(0x28e55400,44)
    assert p.read(0x28e554ac,36)==frozen.read(0x28e554ac,36)
    p.put(0x28e626f3,b'C','IORC revision')
    c,sc=m4asm.assemble_module(str(ROOT/'src/m4/io_level_r12_edit_view.s'))
    addr=p.add(c)
    p.chain_ptr(0x28d96da0,orig[0x28d96da0],after=addr+sc['edit_top'])
    p.chain_ptr(0x28d96e38,orig[0x28d96e38],after=addr+sc['edit_params'])
    p.finish_chains()
    new=p.output()[0]
    # Preserve old segment contents; only the two function pointers, revision,
    # and segment/application integrity headers may change.
    allowed=set(range(24))
    for site in (*orig,0x28e626f3):
        off=p.off(site,1 if site==0x28e626f3 else 4)
        allowed.update(range(off,off+(1 if site==0x28e626f3 else 4)))
    for seg in p.segs:allowed.update(range(seg[0],seg[0]+20))
    changed=[i for i,(x,y) in enumerate(zip(old,new)) if x!=y and i<len(old)-8]
    assert set(changed)<=allowed,[(hex(i),old[i],new[i]) for i in changed if i not in allowed]
    # Validate stock paint/dsp/gr callbacks and all other original application bytes.
    import hxf_ram as hr
    ss,_=hr.app_segments(old);ds,_=hr.app_segments(new)
    assert next(b for a,b in ss if a==0x20000000)==next(b for a,b in ds if a==0x20000000)
    new=bytes(new)
    result,_,_=l6ia.rebuild_archive(arch,{0:bytes(new)})
    assert all(pa.get_entry_swapped(result,i)==pa.get_entry_swapped(arch,i) for i in range(1,15))
    assert pa.get_entry_swapped(result,0)==bytes(new)
    out=ROOT/'build/browser-ramrun'/NAME;out.mkdir(parents=True,exist_ok=True)
    f=out/(NAME+'.hxf');l=out/(NAME+'.l6ia');l.write_bytes(result)
    subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(l)],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(l),str(f),'--donor',str(FROZEN)],check=True,stdout=subprocess.DEVNULL)
    got,was=pa.load_l6ia_from_any(str(f));assert was and got==result
    meta=json.loads((R11.parent/'manifest-build.json').read_text())
    meta.update(variant=NAME,HXF_SHA256=sha(f.read_bytes()),L6IA_SHA256=sha(result),exact_R11_SHA256=R11_SHA,R11_SHARC_byte_identical=True,edit_hooks={hex(k):hex(v) for k,v in orig.items()},edit_module_address=hex(addr),edit_module_bytes=len(c),edit_handler_addresses={k:hex(addr+sc[k]) for k in ("edit_top","edit_params","edit_draw")},edit_meter_rows=[128,132],play_meter_rows=[113,117],hardware_tested=False)
    (out/'manifest-build.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
if __name__=='__main__':build()
