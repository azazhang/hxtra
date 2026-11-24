#!/usr/bin/env python3
"""R10: R09 exact SHARC and M4 except six-byte input-call guard and IORA magic."""
import json,subprocess,sys,struct,zlib
import m4asm,patch_amp as pa,patch_menu as pm,l6ia
from build_io_level_r09_direct_meter import ROOT,FROZEN,FROZEN_SHA256,R05,R05_SHA,sha
NAME='IO-LEVEL-R10-DIRECT-PEAK-RECEIVER-FIX'
R09_NAME='IO-LEVEL-R09-DIRECT-SHARC-PEAK-METERS'
R09=ROOT/'build/browser-ramrun'/R09_NAME/(R09_NAME+'.hxf')
R09_SHA='9c414ad9fcb238a2550445c37b42de0cc9f8eeb0c7b79f6f3a06e32c015425bc'
BASE=0x28e62324
def build():
    assert sha(R09.read_bytes())==R09_SHA and sha(FROZEN.read_bytes())==FROZEN_SHA256
    arch,h=pa.load_l6ia_from_any(str(R09));assert h
    donor,h=pa.load_l6ia_from_any(str(FROZEN));assert h
    old=pa.get_entry_swapped(arch,0)
    p=pm.Patch(old,[],{},lambda i:pa.get_entry_swapped(arch,i))
    a,sa=m4asm.assemble_module(str(ROOT/'src/m4/io_level_r09_direct_meter.s'))
    b,sb=m4asm.assemble_module(str(ROOT/'src/m4/io_level_r10_direct_meter.s'))
    assert sa==sb and len(a)==len(b) and p.read(BASE,len(a))==a
    changed=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
    assert set(changed)<=set(range(174,180))|{sa['r09_stats']+3}
    off=p.off(BASE,len(a));new=bytearray(old);new[off:off+len(a)]=b
    size=struct.unpack_from("<I",new,4)[0]
    struct.pack_into("<I",new,8,zlib.crc32(new[0x34:size]))
    result,_,_=l6ia.rebuild_archive(arch,{0:bytes(new)})
    assert all(pa.get_entry_swapped(result,i)==pa.get_entry_swapped(arch,i) for i in range(1,15))
    assert pa.get_entry_swapped(result,0)==bytes(new)
    out=ROOT/'build/browser-ramrun'/NAME;out.mkdir(parents=True,exist_ok=True)
    f=out/(NAME+'.hxf');l=out/(NAME+'.l6ia');l.write_bytes(result)
    subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(l)],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(l),str(f),'--donor',str(FROZEN)],check=True,stdout=subprocess.DEVNULL)
    got,was=pa.load_l6ia_from_any(str(f));assert was and got==result
    meta=json.loads((R09.parent/'manifest-build.json').read_text())
    meta.update(variant=NAME,HXF_SHA256=sha(f.read_bytes()),L6IA_SHA256=sha(result),exact_R09_SHA256=R09_SHA,R09_SHARC_byte_identical=True,changed_M4_addresses=[hex(BASE+i) for i in changed],changed_M4_byte_count=len(changed),hardware_tested=False)
    (out/'manifest-build.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
if __name__=='__main__':build()
