#!/usr/bin/env python3
"""R02D exact-donor SHARC patch that never lengthens the eMMC Entry2 payload.

The first R02C/R02C-HWFAIL02 SHARC bootstream expanded 524212 -> 524284
bytes while the RAM overlay left its installed eMMC metadata sector (at
0x8802) advertising 524212 bytes. The resulting firmware failed startup twice.

R02D confines all changes to Entry2, preserves its original byte length,
and independently checks byte-for-byte-equivalent final DM/PM initialization
except for a single metronome branch and 14 otherwise unused PM words.

It uses seven nonoverlapping merges of physically adjacent original LDR
initialization ranges, saving exactly 84 bytes, to fit 14 added PM words (84
bytes) into existing contiguous PM block 197. It never changes model data,
global settings, installed M4 code or other firmware entries. No device I/O.
"""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,sys
import patch_amp as pa,l6ia,sasm
from metro_led_donor_patch import DONOR_MD5,DONOR_SHA256
from metro_led_sharc_patch import parse_ldr,as_words,pm_words,initialized_ram

ROOT=Path(__file__).resolve().parent.parent
DONOR_ENTRY2_BYTES=524212
PM_MAIN=0xe5386
PM_SHIM=0xe52c4
# All groups are exact adjacent physical addresses. They may appear out of
# order in the LDR file but are initialized before FINAL_INIT execution.
GROUPS=(
 (192,191,194,193),  # 4 contiguous 8-word primitive descriptors; save36
 (200,199),          # 2 contiguous 8-word primitive descriptors; save12
 (187,189),          # adjacent 21+94-word DM initialization; save12
 (188,190),          # adjacent PM code sections 46+152; save12
 (180,177),          # adjacent PM code sections 152+142; save12
)
assert sum((len(g)-1)*12 for g in GROUPS)==84

def merge_blocks(blocks,group,replace_pm=None):
    chain=[blocks[j] for j in group]
    t=chain[0][0];assert t in (4,5) and all(x[0]==t for x in chain)
    for x,y in zip(chain,chain[1:]):assert x[2]+x[1]==y[2],(group,x,y)
    addr=chain[0][2]
    if t==4:
        words=[z for b in chain for z in b[3][3:]]
        packed=pa.pack_init_l32(addr,words)
    else:
        words=[z for b in chain for z in pm_words(b)]
        if replace_pm is not None:
            assert addr<=PM_MAIN and PM_MAIN+142<=addr+len(words)
            off=PM_MAIN-addr
            for k,word in enumerate(replace_pm):words[off+k]=word
        packed=pa.pack_init_l48(addr,words)
    assert packed[:3]==[t,sum(x[1] for x in chain),addr]
    return (t,packed[1],addr,tuple(packed))


def sharc_preserve_size(archive):
    E=l6ia.parse(archive);orig=archive[E[2]['payload_off']:E[2]['payload_off']+E[2]['payload_len']]
    assert len(orig)==DONOR_ENTRY2_BYTES
    blocks,prefix,tail=parse_ldr(orig)
    assert len(blocks)==201
    orig_dm,orig_pm=initialized_ram(blocks)
    donor_source=subprocess.check_output(['git','show','df327d5:src/sharc/click.asm'],cwd=ROOT,text=True).replace('KIT_PM_BASE',hex(PM_MAIN))
    orig_sects,_=sasm.assemble(donor_source,'donor_v121_click.asm')
    assert list(blocks[177][3])==pa.pack_init_l48(PM_MAIN,orig_sects[0].words)
    new_source=(ROOT/'src/sharc/click_led_egress_compact.asm').read_text().replace('KIT_PM_BASE',hex(PM_MAIN)).replace('LED_PROBE_BASE',hex(PM_SHIM))
    secs,syms=sasm.assemble(new_source,'click_led_egress_compact.asm')
    assert len(secs)==2
    main,shim=secs
    assert (main.kind,main.addr,len(main.words))==('pm',PM_MAIN,142)
    assert (shim.kind,shim.addr,len(shim.words))==('pm',PM_SHIM,14)
    changed=[i for i,(a,b) in enumerate(zip(orig_sects[0].words,main.words)) if a!=b]
    assert changed==[73],changed
    assert PM_SHIM==blocks[197][2]+blocks[197][1]
    assert set(range(PM_SHIM,PM_SHIM+14)).isdisjoint(orig_pm)
    new=list(blocks)
    discarded=set()
    for group in GROUPS:
        assert all(j not in discarded for j in group)
        replacement=main.words if 177 in group else None
        merged=merge_blocks(blocks,group,replace_pm=replacement)
        keep=max(group)
        discarded.update(set(group)-{keep})
        new[keep]=merged
    # Put the 14-word extension into existing adjacent PM block197, so the
    # SHARC bootloader sees no extra INIT_L48 command, just a longer known one.
    pm=pm_words(blocks[197]);pm.extend(shim.words)
    assert len(pm)==434
    packed=pa.pack_init_l48(blocks[197][2],pm)
    new[197]=(5,434,blocks[197][2],tuple(packed))
    final=[x for i,x in enumerate(new) if i not in discarded]
    assert len(final)==201-7,len(final)
    revised=as_words(final,prefix,tail)
    assert len(revised)==len(orig)==DONOR_ENTRY2_BYTES,(len(revised),len(orig))
    result_dm,result_pm=initialized_ram(final)
    assert orig_dm==result_dm, 'original DM RAM initialization values affected'
    discrepancies={a for a in set(orig_pm)|set(result_pm) if orig_pm.get(a)!=result_pm.get(a)}
    expected={PM_MAIN+changed[0]}|set(range(PM_SHIM,PM_SHIM+14))
    assert discrepancies==expected,(len(discrepancies),sorted(discrepancies^expected)[:20])
    # Ensure no unmodified PM or DM boot command moved beyond the last 512B
    # block compared with donor. This remains an exact same-size bootstream.
    out,_,_=l6ia.rebuild_archive(archive,{2:l6ia.swap32(revised)})
    e2=l6ia.parse(out)[2]
    assert e2['payload_len']==DONOR_ENTRY2_BYTES
    for i in range(15):
        if i!=2:assert pa.get_entry_swapped(out,i)==pa.get_entry_swapped(archive,i)
    return out,{
      'original_entry2_bytes':len(orig),'patched_entry2_bytes':len(revised),
      'entry2_size_delta':0,'original_ldr_blocks':len(blocks),'patched_ldr_blocks':len(final),
      'reduced_ldr_descriptor_count':7,'saved_ldr_header_bytes':84,
      'shim_original_footprint_bytes':84,'shim_PM_addrs':[hex(PM_SHIM),hex(PM_SHIM+14)],
      'original_metronome_changed_instruction_addr':hex(PM_MAIN+changed[0]),
      'initialized_DM_words_unchanged':len(orig_dm),
      'initialized_PM_addresses_changed_exactly':len(discrepancies),
      'other_entries_byte_identical':14}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('donor');ap.add_argument('output')
    args=ap.parse_args()
    raw=Path(args.donor).read_bytes()
    assert hashlib.md5(raw).hexdigest()==DONOR_MD5
    assert hashlib.sha256(raw).hexdigest()==DONOR_SHA256
    archive,yes=pa.load_l6ia_from_any(args.donor)
    assert yes
    out,info=sharc_preserve_size(archive)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_bytes(out)
    print(json.dumps({'name':'METRO-LEDSYNC-R02D-SHARC-SIZE-PRESERVED','hardware_tested':False,'output':args.output,'SHA256':hashlib.sha256(out).hexdigest(),**info},indent=2))
if __name__=='__main__':main()
