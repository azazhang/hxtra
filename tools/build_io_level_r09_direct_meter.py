#!/usr/bin/env python3
"""R09: exact R03C plus direct SHARC graph peaks and bounded M4 presentation.

Replace the zero-filled NAM scratch record by an equivalent zero initialization
and the added code/state. Keep original bootstream length and every subsequent
record offset. No other original DSP instruction except two hook slots changes.
No device access.
"""
from pathlib import Path
import hashlib,json,struct,subprocess,sys
import patch_amp as pa,patch_menu as pm,l6ia,setting_ids,sasm,block3
from metro_led_sharc_patch import parse_ldr,as_words,pm_words
from build_io_level_r07_native_peak_retention import R05,R05_SHA,FROZEN,FROZEN_SHA256,ROOT
import hxf_ram as hr
NAME='IO-LEVEL-R09-DIRECT-SHARC-PEAK-METERS'
M4SRC='src/m4/io_level_r09_direct_meter.s'
DSPSRC=ROOT/'src/sharc/io_level_r09_direct_peaks.asm'
RX,HOME,REG=0x28da6134,0x28d96e28,0x28d96adc
GR_HOME=0x28e55451
sha=lambda x:hashlib.sha256(x).hexdigest()
def record(words):
    return (*words[:3],tuple(words))
def physical(b):
    t,n,a,_=b
    if t in (2,5) and 0xe0000<=a<0xf0000:return block3.nw(a),block3.nw(a+((n+1)&~1))
    if t in (1,4) and 0xe0000<=a<0xf0000:return a,a+n
    return None
def patch_dsp(arch):
    e=l6ia.parse(arch)[2];raw=arch[e['payload_off']:e['payload_off']+e['payload_len']]
    old,pre,tail=parse_ldr(raw)
    assert len(old)==201 and len(raw)==524212
    assert old[168][:3]==(4,796,0xc7ce0) and set(old[168][3][3:])=={0}
    secs,syms=sasm.assemble(DSPSRC.read_text(),str(DSPSRC))
    assert len(secs)==2 and [s.kind for s in secs]==['dm','pm']
    dm,code=secs
    assert dm.addr==0xe7440 and code.addr==0xe4da0
    padded=code.words+[0]*(len(code.words)%2)
    add=[record(pa.pack_init_l32(dm.addr,dm.words)),record(pa.pack_init_l48(code.addr,padded))]
    ranges=[physical(b) for b in add]
    assert all(x and 0xe743e<=x[0]<x[1]<=0xe7639 for x in ranges)
    assert ranges[0][1]<=ranges[1][0]
    for a,z in ranges:
        for b in old:
            r=physical(b)
            if r:assert z<=r[0] or a>=r[1],(r,b[:3],a,z)
    # Substitution has exactly the original record footprint. Zero-fill a
    # prefix of the original scratch region; initialize all remaining words
    # with the original explicit zeros; initialize new non-overlapping ranges.
    k=sum(len(x[3]) for x in add)+3
    assert 0<k<796
    replacement=[record([1,k,0xc7ce0]),*add,record([4,796-k,0xc7ce0+k]+[0]*(796-k))]
    assert sum(len(b[3]) for b in replacement)==len(old[168][3])
    assert replacement[0][2]+replacement[0][1]==replacement[-1][2]
    assert replacement[-1][2]+replacement[-1][1]==0xc7ce0+796
    new=old.copy()
    hooks,_=sasm.assemble(f'.section pm 0xe4f6f\n CALL {syms["INPUT_PEAK"]:#x};\n.section pm 0xe503c\n CALL {syms["MAIN_PEAK"]:#x};','hooks')
    for i,h,expected in zip((183,190),hooks,(0x1014000e763d,0x1000000e7795)):
        b=old[i];assert b[0]==5
        idx=h.addr-b[2];orig=pm_words(b);assert orig[idx]==expected and len(h.words)==1
        buf=bytearray(struct.pack('<%dI'%len(b[3]),*b[3]))
        buf[12+6*idx:18+6*idx]=h.words[0].to_bytes(6,'little')
        new[i]=record(struct.unpack('<%dI'%(len(buf)//4),buf))
        orig[idx]=h.words[0];assert pm_words(new[i])==orig
    new[168:169]=replacement
    assert len(new)==204 and new[:168]==old[:168]
    for i in range(169,len(old)):
        if i not in (183,190):assert new[i+3]==old[i]
    newraw=as_words(new,pre,tail)
    assert len(newraw)==len(raw) and parse_ldr(newraw)==(new,pre,tail)
    result,_,_=l6ia.rebuild_archive(arch,{2:l6ia.swap32(newraw)})
    assert all(pa.get_entry_swapped(result,i)==pa.get_entry_swapped(arch,i) for i in range(15) if i!=2)
    return result,{'SHARC_entry2_bytes':len(raw),'original_LDR_records':len(old),'new_LDR_records':len(new),'original_record_offsets_preserved':True,'zero_fill_prefix_words':k,'zero_fill_original_words':796,'new_DM_words':len(dm.words),'new_PM_words':len(padded),'new_physical_ranges':[[hex(a),hex(z)] for a,z in ranges],'SHARC_hooks':[hex(h.addr) for h in hooks],'actual_changed_payload_sectors':[i for i in range(1024) if raw[i*512:(i+1)*512]!=newraw[i*512:(i+1)*512]]}
def patch_m4(arch,frozen):
    read=lambda n:pa.get_entry_swapped(arch,n)
    old=read(0);p=pm.Patch(old,[],{},read)
    old_rx=p.u32(RX);old_home=p.u32(HOME)
    r=p.read(REG,4);old_reg=setting_ids.bl_targets(struct.unpack('<2H',r),REG)[0]
    assert old_rx&1 and old_home&1 and old_home!=GR_HOME and pm.bl(REG,old_reg)==r
    assert pm.Patch(pa.get_entry_swapped(frozen,0),[],{},lambda i:pa.get_entry_swapped(frozen,i)).u32(HOME)==GR_HOME
    m=p.module(M4SRC)
    # Replace only the R05 paint subscriber, retain the original R03C chain.
    home=p.add(pm.chain_cave(p.next(),GR_HOME&~1,[],[m['r09_draw']]))
    p.put(HOME,struct.pack('<I',home|1),'original GR/Home plus direct meters')
    p.chain_ptr(RX,old_rx,before=m['r09_frame'])
    p.chain_bl(REG,old_reg,after=m['r09_register'])
    p.finish_chains();repl=p.output();assert set(repl)=={0}
    new=repl[0];allowed=set(range(24))
    for site in (RX,HOME,REG):off=p.off(site,4);allowed.update(range(off,off+4))
    for s in p.segs:allowed.update(range(s[0],s[0]+20))
    assert not [i for i,(a,b) in enumerate(zip(old,new)) if a!=b and i<len(old)-8 and i not in allowed]
    ss,_=hr.app_segments(old);ds,_=hr.app_segments(new)
    assert next(b for a,b in ss if a==0x20000000)==next(b for a,b in ds if a==0x20000000)
    out,_,_=l6ia.rebuild_archive(arch,repl)
    assert all(pa.get_entry_swapped(out,i)==read(i) for i in range(1,15))
    return out,{'M0_segment_identical':True,'native_R05_ledger_preserved':True,'R03C_GR_Home_preserved':True,'M4_hook_sites':[hex(RX),hex(HOME),hex(REG)],'M4_symbols':{k:hex(m[k]) for k in ('r09_frame','r09_draw','r09_stats','r09_register')}}
def build():
    assert sha(FROZEN.read_bytes())==FROZEN_SHA256 and sha(R05.read_bytes())==R05_SHA
    donor,h=pa.load_l6ia_from_any(str(FROZEN));r05,h2=pa.load_l6ia_from_any(str(R05));assert h and h2
    assert [i for i in range(15) if pa.get_entry_swapped(donor,i)!=pa.get_entry_swapped(r05,i)]==[0]
    a,meta=patch_dsp(r05);result,m4=patch_m4(a,donor);meta.update(m4)
    assert [i for i in range(15) if pa.get_entry_swapped(donor,i)!=pa.get_entry_swapped(result,i)]==[0,2]
    out=ROOT/'build/browser-ramrun'/NAME;out.mkdir(parents=True,exist_ok=True)
    l=out/(NAME+'.l6ia');f=out/(NAME+'.hxf');l.write_bytes(result)
    subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(l)],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(l),str(f),'--donor',str(FROZEN)],check=True,stdout=subprocess.DEVNULL)
    got,was=pa.load_l6ia_from_any(str(f));assert was and got==result
    meta.update(variant=NAME,donor_R03C_SHA256=FROZEN_SHA256,exact_R05_SHA256=R05_SHA,HXF_SHA256=sha(f.read_bytes()),L6IA_SHA256=sha(result),other_13_entries_identical=True,modified_entries_vs_R03C=[0,2],hardware_tested=False,ram_only=True)
    (out/'manifest-build.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
if __name__=='__main__':build()
