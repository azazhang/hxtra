#!/usr/bin/env python3
"""Exact HXtra v1.2.1 SHARC Entry2 delta, preserving other SHARC code.

The donor Entry2 eMMC bootstream is 524212/524288 bytes. Its original 142-word
metronome kernel can be identified exactly (binary compare to repo commit
df327d5). We overwrite ONE SHARC instruction with a jump to a 15-word event
hook in an otherwise unused PM-address gap. An equivalent four-descriptor
LDR data initialization is compressed 36 bytes, just fitting the 108-byte hook.
No SHARC/FX models, USB monitor, NAM, GR or settings are dropped or rebuilt.
This script has no device access.
"""
import argparse,hashlib,struct,subprocess
from pathlib import Path
import patch_amp as pa
import l6ia
import sasm
from metro_led_donor_patch import DONOR_MD5,DONOR_SHA256,donor_patch

ROOT=Path(__file__).resolve().parent.parent
ENTRY2_MAX=524288
METRO_PM=0xe5386
SHIM_PM=0xe52c4
SHIM_UPPER=0xe52ee

def nwords(tag,cnt):
    return {5:((cnt+1)&~1)*3//2,4:cnt,3:(cnt+1)//2,6:cnt*2,10:cnt,9:cnt}.get(tag,0)


def parse_ldr(raw):
    assert len(raw)%4==0
    w=struct.unpack('<%dI'%(len(raw)//4),raw)
    i=384
    blocks=[]
    while i+3<=len(w):
        tag,cnt,addr=w[i:i+3]
        assert tag in range(13),(i,tag)
        if tag==0:
            # Preserve the entire untouched FINAL_INIT tail verbatim.
            break
        n=3+nwords(tag,cnt)
        assert i+n<=len(w),(i,tag,cnt,n)
        blocks.append((tag,cnt,addr,tuple(w[i:i+n])))
        i+=n
    assert i<len(w), 'FINAL_INIT absent'
    return blocks,tuple(w[:384]),tuple(w[i:])


def as_words(blocks,prefix,tail):
    flat=list(prefix)
    for _,_,_,data in blocks:flat.extend(data)
    flat.extend(tail)
    return struct.pack('<%dI'%len(flat),*flat)


def pm_words(block):
    tag,cnt,addr,words=block
    assert tag==5
    data=struct.pack('<%dI'%(len(words)-3),*words[3:])
    return [int.from_bytes(data[6*i:6*(i+1)],'little') for i in range(cnt)]


def initialized_ram(blocks):
    """Final DM & PM values in ordered LDR INIT_L32/INIT_L48 instructions.

    The same tags and all other blocks are compared verbatim. Reordering
    four independent data descriptors has no effect on final initialized RAM.
    """
    dm={};pm={}
    for tag,cnt,addr,data in blocks:
        if tag==4:
            for i,value in enumerate(data[3:]):dm[addr+i]=value
        if tag==5:
            for i,value in enumerate(pm_words((tag,cnt,addr,data))):pm[addr+i]=value
    return dm,pm


def sharc_patch(archive):
    ent=pa.l6ia.parse(archive)[2]
    old_e2=archive[ent['payload_off']:ent['payload_off']+ent['payload_len']]
    # SHARC LDR tags are in the wire-order original payload. get_entry_swapped
    # returns the archive's opposite byte order and is not directly parseable.
    assert len(old_e2)==524212,('wrong donor Entry2 size',len(old_e2))
    blocks,prefix,tail=parse_ldr(old_e2)
    assert len(blocks)==201
    assert [(blocks[i][0],blocks[i][1],blocks[i][2]) for i in (177,191,192,193,194)]==[
         (5,142,METRO_PM),(4,8,0x200020),(4,8,0x200018),(4,8,0x200030),(4,8,0x200028)]
    src_orig=subprocess.check_output(['git','show','df327d5:src/sharc/click.asm'],cwd=ROOT,text=True)
    orig_sects,_=sasm.assemble(src_orig.replace('KIT_PM_BASE',hex(METRO_PM)),'donor_v121_click.asm')
    assert len(orig_sects)==1 and orig_sects[0].addr==METRO_PM and len(orig_sects[0].words)==142
    assert list(blocks[177][3])==pa.pack_init_l48(METRO_PM,orig_sects[0].words), 'installed kernel differs from exact v1.2.1 source'

    src=(ROOT/'src/sharc/click_led_egress.asm').read_text()
    secs,syms=sasm.assemble(src.replace('KIT_PM_BASE',hex(METRO_PM)).replace('LED_PROBE_BASE',hex(SHIM_PM)),'click_led_egress.asm')
    assert len(secs)==2 and all(s.kind=='pm' for s in secs)
    main,shim=secs
    assert (main.addr,len(main.words))==(METRO_PM,142)
    assert shim.addr==SHIM_PM and SHIM_PM+len(shim.words)<=SHIM_UPPER
    modified=[i for i,(a,b) in enumerate(zip(orig_sects[0].words,main.words)) if a!=b]
    assert len(modified)==1,('donor SHARC metronome altered beyond single trampoline',modified)
    assert (main.addr+modified[0])==syms['CUSTOM_AMP_ENTRY']+modified[0]
    # Donor PM gap lies between two populated blocks; no initialization may
    # target any address of the new shim.
    orig_dm,orig_pm=initialized_ram(blocks)
    assert not (set(range(SHIM_PM,SHIM_PM+len(shim.words))) & set(orig_pm))
    assert set(range(SHIM_PM,SHIM_UPPER)).isdisjoint(orig_pm)
    new=list(blocks)
    packed_main=pa.pack_init_l48(METRO_PM,main.words)
    new[177]=(5,142,METRO_PM,tuple(packed_main))
    # Four adjacent, non-overlapping, 8-word LDR data records at tail positions
    # are assembled into one 32-word LDR record with exact same final DM RAM.
    chunk=[blocks[k] for k in (191,192,193,194)]
    ascending=sorted(chunk,key=lambda b:b[2])
    assert [b[2] for b in ascending]==[0x200018,0x200020,0x200028,0x200030]
    merged=[]
    for b in ascending:
        assert b[0]==4 and b[1]==8 and len(b[3])==11
        merged.extend(b[3][3:])
    packed=pa.pack_init_l32(0x200018,merged)
    assert len(packed)==35
    new[191:195]=[(4,32,0x200018,tuple(packed))]
    shim_packed=pa.pack_init_l48(SHIM_PM,shim.words)
    assert len(shim_packed)==3+(16*3//2),len(shim_packed)
    new.append((5,16,SHIM_PM,tuple(shim_packed)))
    assert len(new)==199 # 201 -3 +1
    updated=as_words(new,prefix,tail)
    assert len(updated)==len(old_e2)+len(shim_packed)*4-3*3*4==524284,(len(updated),len(old_e2))
    assert len(updated)<=ENTRY2_MAX
    candidate_dm,candidate_pm=initialized_ram(new)
    assert candidate_dm==orig_dm,'SHARC DM initialization changed'
    differences={a for a in set(orig_pm)|set(candidate_pm) if orig_pm.get(a)!=candidate_pm.get(a)}
    assert differences==set(range(SHIM_PM,SHIM_PM+16))|{METRO_PM+modified[0]}, (len(differences),sorted(differences)[:20])
    assert candidate_pm[SHIM_PM+15]==0, 'odd-length PM shim padded with a mandatory NOP'
    for i,(old,new_) in enumerate(zip(blocks,new[:191])):
        if i!=177:assert old==new_,('other SHARC LDR instructions modified',i)
    arch,_,_=l6ia.rebuild_archive(archive,{2:l6ia.swap32(updated)})
    ent2=pa.l6ia.parse(arch)[2]
    assert arch[ent2['payload_off']:ent2['payload_off']+ent2['payload_len']]==updated
    for i in (0,1,*range(3,15)):
        assert pa.get_entry_swapped(arch,i)==pa.get_entry_swapped(archive,i), ('altered nondsp entry',i)
    return arch,{
        'original_entry2_bytes':len(old_e2),'revised_entry2_bytes':len(updated),
        'partition_limit':ENTRY2_MAX,'partition_headroom_bytes':ENTRY2_MAX-len(updated),
        'original_kernel_sha256':hashlib.sha256(struct.pack('<%dQ'%len(orig_sects[0].words),*orig_sects[0].words)).hexdigest(),
        'donor_kernel_words':142,'modified_kernel_instruction_addresses':[hex(METRO_PM+i) for i in modified],
        'shim_pm_start':hex(SHIM_PM),'shim_pm_end_exclusive':hex(SHIM_PM+len(shim.words)),
        'shim_instructions':len(shim.words), 'freed_bytes_via_semantically_identical_dm_merge':36,
        'dma_initialized_dm_addresses_identical':len(orig_dm),
        'original_initialized_pm_instruction_count':len(orig_pm),
        'changed_initialized_pm_instruction_addresses':len(differences),
        'other_l6ia_entries_untouched':14}


def main():
    import json
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('donor')
    a.add_argument('out')
    opt=a.parse_args()
    data=Path(opt.donor).read_bytes()
    assert hashlib.md5(data).hexdigest()==DONOR_MD5
    assert hashlib.sha256(data).hexdigest()==DONOR_SHA256
    archive,yes=pa.load_l6ia_from_any(opt.donor)
    assert yes
    m4,m4_report=donor_patch(archive)
    out,e2_report=sharc_patch(m4)
    assert pa.get_entry_swapped(out,0)==pa.get_entry_swapped(m4,0)
    for n in range(3,15):assert pa.get_entry_swapped(out,n)==pa.get_entry_swapped(archive,n)
    Path(opt.out).write_bytes(out)
    print(json.dumps({'status':'offline donor-preserving SHARC+M4 analysis build; NO hardware run',
       **m4_report,**e2_report,'output':str(opt.out),'sha256':hashlib.sha256(out).hexdigest()},indent=2))

if __name__=='__main__':main()
