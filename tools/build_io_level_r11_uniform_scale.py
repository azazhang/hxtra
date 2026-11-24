#!/usr/bin/env python3
"""R11: exact physical R10 with uniform 5 dB lookup table and equivalent paint diagnostic."""
import json,subprocess,sys,struct,zlib
import m4asm,patch_amp as pa,patch_menu as pm,l6ia
from build_io_level_r09_direct_meter import ROOT,FROZEN,FROZEN_SHA256,R05,R05_SHA,sha
NAME='IO-LEVEL-R11-UNIFORM-5DB-PEAK-METERS'
R10_NAME='IO-LEVEL-R10-DIRECT-PEAK-RECEIVER-FIX'
R10=ROOT/'build/browser-ramrun'/R10_NAME/(R10_NAME+'.hxf')
R10_SHA='45f44a7e8a2ea442beff5b4776f25eb4264cdf37e67e9ec9871b0882a75b82d4'
BASE=0x28e62324
def build():
    assert sha(R10.read_bytes())==R10_SHA and sha(FROZEN.read_bytes())==FROZEN_SHA256
    arch,h=pa.load_l6ia_from_any(str(R10));assert h
    donor,h=pa.load_l6ia_from_any(str(FROZEN));assert h
    old=pa.get_entry_swapped(arch,0)
    p=pm.Patch(old,[],{},lambda i:pa.get_entry_swapped(arch,i))
    a,sa=m4asm.assemble_module(str(ROOT/'src/m4/io_level_r10_direct_meter.s'))
    b,sb=m4asm.assemble_module(str(ROOT/'src/m4/io_level_r11_direct_meter.s'))
    assert sa==sb and len(a)==len(b) and p.read(BASE,len(a))==a
    changed=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
    level=sa['r09_levels'];paint=sa['r09_draw_bg']-14
    # Locate the exact diagnostic comparison within the paint callback.
    cmpbytes=bytes.fromhex('062d')
    matches=[i for i in range(sa['r09_draw'],sa['r09_draw_bg'],2) if a[i:i+2]==cmpbytes]
    assert len(matches)==1
    paint=matches[0]
    assert b[paint:paint+2]==bytes.fromhex('0a2d')
    assert set(changed)<=set(range(level,level+64))|{paint,sa['r09_stats']+3}
    assert list(struct.unpack_from('<16f',b,level))==[struct.unpack('<f',struct.pack('<f',10**(d/20)))[0] for d in range(-75,1,5)]
    assert a[level+60:level+64]==b[level+60:level+64]
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
    meta=json.loads((R10.parent/'manifest-build.json').read_text())
    meta.update(variant=NAME,HXF_SHA256=sha(f.read_bytes()),L6IA_SHA256=sha(result),exact_R10_SHA256=R10_SHA,R10_SHARC_byte_identical=True,changed_M4_addresses=[hex(BASE+i) for i in changed],changed_M4_byte_count=len(changed),hardware_tested=False,scale_dbfs=list(range(-75,1,5)),hot_paint_threshold_segments=10,hot_paint_threshold_dbfs=-30)
    (out/'manifest-build.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
if __name__=='__main__':build()
