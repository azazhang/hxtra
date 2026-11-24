#!/usr/bin/env python3
"""Offline R07: exact working R05 M4, stock peak retained on queue full.

Patch only seven existing SHARC instruction slots, in-place. No firmware
installation, settings changes, or new LDR records. R06 is not included.
"""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/sharc')]
import l6ia,patch_amp as pa,sasm
from metro_led_sharc_patch import parse_ldr,as_words,pm_words
from build_io_level_r01_native_frame_probe import FROZEN,FROZEN_SHA256
NAME='IO-LEVEL-R07-NATIVE-PEAK-QUEUE-RETENTION'
R05_NAME='IO-LEVEL-R05-LIVE-INPUT-OUTPUT-CANDIDATE-BARS'
R05=ROOT/'build/browser-ramrun'/R05_NAME/(R05_NAME+'.hxf')
R05_SHA='3eef769a0457cfa1fa4d089a92b0ebab242b0570977d94c13fb155276243112a'
ADDRESS=0x8da7e
BLOCK=6
ORIGINAL=[0xb10100000002,0x06be0408cbb8,0x0f0100000001,0x603e08042333,0x0a3e05000000,0x013e00042000,0xb10000000000]
SRC=ROOT/'src/sharc/native_meter_retain_on_queue_full.asm'
sha=lambda x:hashlib.sha256(x).hexdigest()

def patch(archive):
    e=l6ia.parse(archive)[2]
    raw=archive[e['payload_off']:e['payload_off']+e['payload_len']]
    old,pre,tail=parse_ldr(raw)
    assert len(raw)==524212 and len(old)==201
    assert old[BLOCK][:3]==(5,5125,0x8d680)
    offset=ADDRESS-old[BLOCK][2]
    words=pm_words(old[BLOCK])
    assert words[offset:offset+7]==ORIGINAL
    secs,_=sasm.assemble(SRC.read_text(),str(SRC))
    assert len(secs)==1 and secs[0].addr==ADDRESS and len(secs[0].words)==7
    new_words=words.copy();new_words[offset:offset+7]=secs[0].words
    # Keep the existing packed final padding bytes intact as well.
    import struct
    b=bytearray(struct.pack('<%dI'%len(old[BLOCK][3]),*old[BLOCK][3]))
    start=12+6*offset
    b[start:start+42]=b''.join(x.to_bytes(6,'little') for x in secs[0].words)
    new=old.copy();new[BLOCK]=(*old[BLOCK][:3],struct.unpack('<%dI'%(len(b)//4),b))
    assert pm_words(new[BLOCK])==new_words
    assert [i for i,(x,y) in enumerate(zip(old,new)) if x!=y]==[BLOCK]
    assert all(a[:3]==b[:3] for a,b in zip(old,new))
    newraw=as_words(new,pre,tail)
    assert len(newraw)==len(raw)
    assert parse_ldr(newraw)==(new,pre,tail)
    out,_,_=l6ia.rebuild_archive(archive,{2:l6ia.swap32(newraw)})
    for n in range(15):
        if n!=2:assert pa.get_entry_swapped(out,n)==pa.get_entry_swapped(archive,n)
    return out,{'SHARC_entry2_bytes':len(raw),'LDR_records':len(old),'LDR_topology_unchanged':True,'changed_LDR_record':BLOCK,'patched_PM_start':hex(ADDRESS),'replaced_instruction_slots':7,'instruction_count_delta':0,'source_SHA256':sha(SRC.read_bytes()),'actual_changed_payload_sectors':[i for i in range(1024) if raw[i*512:(i+1)*512]!=newraw[i*512:(i+1)*512]]}

def build():
    assert sha(FROZEN.read_bytes())==FROZEN_SHA256
    assert sha(R05.read_bytes())==R05_SHA
    donor,h=pa.load_l6ia_from_any(str(FROZEN)); r05,h2=pa.load_l6ia_from_any(str(R05));assert h and h2
    assert [i for i in range(15) if pa.get_entry_swapped(donor,i)!=pa.get_entry_swapped(r05,i)]==[0]
    result,report=patch(r05)
    assert [i for i in range(15) if pa.get_entry_swapped(donor,i)!=pa.get_entry_swapped(result,i)]==[0,2]
    out=ROOT/'build/browser-ramrun'/NAME;out.mkdir(parents=True,exist_ok=True)
    l6=out/(NAME+'.l6ia');hxf=out/(NAME+'.hxf');l6.write_bytes(result)
    subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(l6)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(l6),str(hxf),'--donor',str(FROZEN)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    got,was=pa.load_l6ia_from_any(str(hxf));assert was and got==result
    report.update(variant=NAME,donor_R03C_SHA256=FROZEN_SHA256,exact_R05_SHA256=R05_SHA,HXF_SHA256=sha(hxf.read_bytes()),L6IA_SHA256=sha(result),R05_M4_byte_identical=True,modified_entries_vs_R05=[2],modified_entries_vs_R03C=[0,2],other_13_entries_identical=True,hardware_tested=False,ram_only=True)
    (out/'manifest-build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':build()
