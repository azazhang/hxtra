#!/usr/bin/env python3
"""R03A-SHARC-INPLACE-BOOTCHECK: only change original donor SHARC kernel words.

The original HXtra 1.2.1 LDR image has 201 exact records, Entry2=524212B,
and original click kernel record177 at PM 0xe5386 with 142 instructions.
This builder changes that one record's 142 instruction payload in place,
keeping ALL descriptors, addresses, record lengths and order intact.

NO firmware installation or automatic RAM execution. The M4 donor remains
bit-for-bit original; no new SPI transmitter is present. An active master
packet is not expected in this startup-isolation test.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/sharc')]
import patch_amp as pa,l6ia,sasm
from metro_led_sharc_patch import parse_ldr,as_words
from metro_led_donor_patch import DONOR_MD5,DONOR_SHA256

NAME='METRO-LEDSYNC-R03A-SHARC-INPLACE-BOOTCHECK'
PM_MAIN=0xe5386
EXPECTED_SHARC_BYTES=524212
BLOCK_INDEX=177
REVISION='df327d5'

def donor_patch(archive):
    entries=l6ia.parse(archive)
    assert len(entries)==15
    ent=entries[2]
    original=archive[ent['payload_off']:ent['payload_off']+ent['payload_len']]
    assert len(original)==EXPECTED_SHARC_BYTES
    blocks,prefix,tail=parse_ldr(original)
    assert len(blocks)==201
    assert blocks[BLOCK_INDEX][0:3]==(5,142,PM_MAIN)
    source=subprocess.check_output(['git','show',f'{REVISION}:src/sharc/click.asm'],cwd=ROOT,text=True)
    old,_=sasm.assemble(source.replace('KIT_PM_BASE',hex(PM_MAIN)),'donor_v121_click.asm')
    assert len(old)==1 and len(old[0].words)==142
    old_packed=pa.pack_init_l48(PM_MAIN,old[0].words)
    assert list(blocks[BLOCK_INDEX][3])==old_packed
    new_source=(ROOT/'src/sharc/click_led_r03a_inplace.asm').read_text()
    new,_=sasm.assemble(new_source.replace('KIT_PM_BASE',hex(PM_MAIN)),'r03a_inplace.asm')
    assert len(new)==1 and new[0].kind=='pm'
    assert new[0].addr==PM_MAIN and len(new[0].words)==142
    replacement=pa.pack_init_l48(PM_MAIN,new[0].words)
    assert len(replacement)==len(old_packed)
    changed=[i for i,(a,b) in enumerate(zip(old[0].words,new[0].words)) if a!=b]
    assert 1<=len(changed)<=141
    modified_blocks=list(blocks)
    modified_blocks[BLOCK_INDEX]=(5,142,PM_MAIN,tuple(replacement))
    assert all((a[:3]==b[:3]) for a,b in zip(blocks,modified_blocks))
    assert all(b==modified_blocks[i] for i,b in enumerate(blocks) if i!=BLOCK_INDEX)
    revised=as_words(modified_blocks,prefix,tail)
    assert len(revised)==len(original)==EXPECTED_SHARC_BYTES
    # Explicitly verify byte differences are confined to the EXISTING record177.
    original_words=as_words(blocks,prefix,tail)
    assert original_words==original
    pre=as_words(blocks[:BLOCK_INDEX],prefix,())
    after=as_words(blocks[BLOCK_INDEX+1:],(),tail)
    assert revised.startswith(pre)
    assert revised.endswith(after)
    rec_bytes=len(old_packed)*4
    assert revised[len(pre)+rec_bytes:]==original[len(pre)+rec_bytes:]
    out,_,_=l6ia.rebuild_archive(archive,{2:l6ia.swap32(revised)})
    assert l6ia.parse(out)[2]['payload_len']==EXPECTED_SHARC_BYTES
    for i in range(15):
        if i!=2:
            assert pa.get_entry_swapped(archive,i)==pa.get_entry_swapped(out,i)
    assert [i for i in range(15) if pa.get_entry_swapped(archive,i)!=pa.get_entry_swapped(out,i)]==[2]
    return out,{
        'variant':NAME,'donor_SHA256':DONOR_SHA256,
        'original_SHARC_Entry2_bytes':len(original),
        'candidate_SHARC_Entry2_bytes':len(revised),
        'original_LDR_descriptors':len(blocks),
        'candidate_LDR_descriptors':len(modified_blocks),
        'LDR_topology_changed':False,
        'LDR_order_changed':False,
        'only_modified_LDR_record':BLOCK_INDEX,
        'only_modified_LDR_PM_start':hex(PM_MAIN),
        'PM_record_original_words':142,'PM_record_candidate_words':142,
        'changed_PM_instruction_count':len(changed),
        'changed_PM_instruction_indices':changed,
        'non_SHARC_L6IA_entries_byte_identical':14,
        'M4_donor_unchanged':True,
        'candidate_untested_on_hardware':True,
        'protocol_integrity_proof_complete':False,
        'permanent_firmware_writes':False,
    }

def make(donor:Path,target:Path):
    raw=donor.read_bytes()
    assert hashlib.md5(raw).hexdigest()==DONOR_MD5
    assert hashlib.sha256(raw).hexdigest()==DONOR_SHA256
    arch,is_hxf=pa.load_l6ia_from_any(str(donor))
    assert is_hxf
    candidate,report=donor_patch(arch)
    target.mkdir(parents=True,exist_ok=True)
    l6=target/(NAME+'.l6ia')
    hxf=target/(NAME+'.hxf')
    l6.write_bytes(candidate)
    subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(l6)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(l6),str(hxf),'--donor',str(donor)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    back,is_hxf=pa.load_l6ia_from_any(str(hxf))
    assert is_hxf and back==candidate
    report.update({'hxf_SHA256':hashlib.sha256(hxf.read_bytes()).hexdigest(),
                   'l6ia_SHA256':hashlib.sha256(candidate).hexdigest(),
                   'output_hxf':str(hxf)})
    (target/'manifest-build.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('donor',nargs='?',type=Path,default=Path.home()/'Downloads/HXtra_v1.2.1.hxf')
    a.add_argument('--out',type=Path,default=ROOT/'build/browser-ramrun'/NAME)
    v=a.parse_args()
    print(json.dumps(make(v.donor,v.out),indent=2))

if __name__=='__main__':main()
