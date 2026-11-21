#!/usr/bin/env python3
"""R03B full M4 LED sender + length-preserved SHARC kernel, donor exact.

No on-device effects. All HXF reads from the *user's exact installed* HXtra
v1.2.1. Four vetted M4 hook sites, original untouched features, and one
142-word SHARC LDR record. The 201 LDR headers and 524212B Entry2 length
remain unchanged. Intended for RAM-only user-controlled hardware loading.
"""
from pathlib import Path
import hashlib, json, struct, subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/sharc')]
import patch_amp as pa,patch_menu as pm,l6ia,sasm,usb_commands
from metro_led_sharc_patch import parse_ldr,as_words
from metro_led_donor_patch import DONOR_MD5,DONOR_SHA256
from build_metro_led_r03a_sharc_inplace import PM_MAIN,EXPECTED_SHARC_BYTES,BLOCK_INDEX,REVISION

NAME="METRO-LEDSYNC-R03B-LED-MASTER"
LED_SINK=0x28d98f78
BYPASS=0x28e045a0
REGISTER_ALL_CALL=0x28d96adc
REGISTER_ALL=0x28e1661c
TX_CB_LIT=0x28da6138
PATCH_SITES=(LED_SINK,BYPASS,REGISTER_ALL_CALL,TX_CB_LIT)

def patch_m4(archive):
    read=lambda n:pa.get_entry_swapped(archive,n)
    original=read(0)
    p=pm.Patch(original,[],{},read)
    assert p.read(LED_SINK,4)==bytes.fromhex('85b01a78')
    assert p.read(BYPASS,4)==bytes.fromhex('2de9f041')
    assert p.read(REGISTER_ALL_CALL,4)==pm.bl(REGISTER_ALL_CALL,REGISTER_ALL)
    assert p.read(TX_CB_LIT,4)==struct.pack('<I',0x10000e95)
    assert p.read(0x28d9be92,4)==pm.bl(0x28d9be92,0x28e55060)
    assert p.read(0x28d98f74,4)==pa.thumb_bw(0x28d98f74,0x28e4d632)
    assert p.read(0x28e4d650,6)==bytes.fromhex('0ff294439a79')
    src=ROOT/'src/m4/metronome_led_r03b.s'
    assert src.is_file()
    mod=p.module('src/m4/metronome_led_r03b.s',inc={'usb.inc':usb_commands.inc('metronome_phase')})
    p.put(LED_SINK,pa.thumb_bw(LED_SINK,mod['mp_led_entry']),
          'FS3 post-filter physical LED command after donor TAP visibility')
    p.chain_entry(BYPASS,bytes.fromhex('2de9f041'),after=mod['mp_bypass'])
    p.chain_bl(REGISTER_ALL_CALL,REGISTER_ALL,after=mod['mp_register'])
    p.chain_ptr(TX_CB_LIT,p.u32(TX_CB_LIT),after=mod['mp_tx_stamp'])
    p.finish_chains()
    replaced=p.output()
    assert set(replaced)=={0}
    candidate=replaced[0]
    changes=[i for i,(a,b) in enumerate(zip(original,candidate)) if a!=b]
    allow=set(range(0,24))
    for addr in PATCH_SITES:
        off=p.off(addr,4)
        allow.update(range(off,off+4))
    for seg in p.segs:
        allow.update(range(seg[0],seg[0]+20))
    nonhooks=[i for i in changes if i not in allow and i<len(original)-8]
    assert not nonhooks,(len(nonhooks),nonhooks[:30])
    for name in (b'DSP Usage Display',b'Breathing Line',b'Main+Snd',b'Path A',b'FS1 Hold'):
        assert name in candidate,name
    out,_,_=l6ia.rebuild_archive(archive,replaced)
    for n in range(1,15):
        assert pa.get_entry_swapped(out,n)==read(n),f'unintended Entry{n} M4 patch'
    return out,{
       'M4_changed_hook_sites':[hex(v) for v in PATCH_SITES],
       'donor_existing_original_M4_bytes_changed_only_at_four_sites':True,
       'M4_module_source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
       'M4_new_thumb_symbols':{k:hex(mod[k]) for k in ('mp_led_entry','mp_led_capture','mp_bypass','mp_register','mp_tx_stamp','mp_command')},
       'M4_original_entry0_bytes':len(original),
       'M4_candidate_entry0_bytes':len(candidate),
       'M4_disallowed_donor_byte_mutations':len(nonhooks),
    }

def patch_sharc(archive):
    e=l6ia.parse(archive)[2]
    raw=archive[e['payload_off']:e['payload_off']+e['payload_len']]
    assert len(raw)==EXPECTED_SHARC_BYTES==524212
    blocks,prefix,tail=parse_ldr(raw)
    assert len(blocks)==201
    assert blocks[BLOCK_INDEX][:3]==(5,142,PM_MAIN)
    original_source=subprocess.check_output(['git','show',f'{REVISION}:src/sharc/click.asm'],cwd=ROOT,text=True)
    original,_=sasm.assemble(original_source.replace('KIT_PM_BASE',hex(PM_MAIN)),'original.asm')
    assert len(original)==1 and len(original[0].words)==142
    assert list(blocks[BLOCK_INDEX][3])==pa.pack_init_l48(PM_MAIN,original[0].words)
    source=ROOT/'src/sharc/click_led_r03b_inplace.asm'
    compiled,_=sasm.assemble(source.read_text().replace('KIT_PM_BASE',hex(PM_MAIN)),'r03b.asm')
    assert len(compiled)==1
    new=compiled[0]
    assert new.kind=='pm' and new.addr==PM_MAIN and len(new.words)==142
    assert new.words[-1]==0, 'last padding must be unreachable NOP'
    packed=pa.pack_init_l48(PM_MAIN,new.words)
    assert len(packed)==len(blocks[BLOCK_INDEX][3])
    replaced=list(blocks)
    replaced[BLOCK_INDEX]=(5,142,PM_MAIN,tuple(packed))
    assert all(replaced[i]==b for i,b in enumerate(blocks) if i!=BLOCK_INDEX)
    assert all(b[:3]==r[:3] for b,r in zip(blocks,replaced))
    newraw=as_words(replaced,prefix,tail)
    assert len(newraw)==len(raw)==524212
    a=as_words(blocks[:BLOCK_INDEX],prefix,())
    z=as_words(blocks[BLOCK_INDEX+1:],(),tail)
    assert newraw.startswith(a) and newraw.endswith(z)
    assert newraw[len(a)+len(packed)*4:]==raw[len(a)+len(packed)*4:]
    out,_,_=l6ia.rebuild_archive(archive,{2:l6ia.swap32(newraw)})
    assert l6ia.parse(out)[2]['payload_len']==524212
    for n in range(15):
        if n!=2:assert pa.get_entry_swapped(out,n)==pa.get_entry_swapped(archive,n)
    diff=[i for i,(a,b) in enumerate(zip(original[0].words,new.words)) if a!=b]
    return out,{
       'SHARC_original_entry2_bytes':len(raw),
       'SHARC_candidate_entry2_bytes':len(newraw),
       'SHARC_original_LDR_blocks':len(blocks),
       'SHARC_candidate_LDR_blocks':len(replaced),
       'SHARC_LDR_header_or_order_change':False,
       'SHARC_only_modified_ldr_record':BLOCK_INDEX,
       'SHARC_only_modified_PM_start':hex(PM_MAIN),
       'SHARC_metronome_kernel_PM_words':142,
       'SHARC_modified_instruction_count':len(diff),
       'SHARC_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
       'SHARC_original_nonmetronome_LDR_records_byte_identical':True,
    }

def build(donor=None,out=None):
    donor=Path(donor or Path.home()/'Downloads/HXtra_v1.2.1.hxf')
    out=Path(out or ROOT/'build/browser-ramrun'/NAME)
    data=donor.read_bytes()
    assert hashlib.md5(data).hexdigest()==DONOR_MD5
    assert hashlib.sha256(data).hexdigest()==DONOR_SHA256
    arch,was_hxf=pa.load_l6ia_from_any(str(donor))
    assert was_hxf
    orig=arch
    arch,report_m4=patch_m4(arch)
    arch,report_sharc=patch_sharc(arch)
    diffs=[i for i in range(15) if pa.get_entry_swapped(orig,i)!=pa.get_entry_swapped(arch,i)]
    assert diffs==[0,2],diffs
    for i in range(1,15):
        if i!=2:assert pa.get_entry_swapped(orig,i)==pa.get_entry_swapped(arch,i)
    out.mkdir(parents=True,exist_ok=True)
    l6=out/(NAME+'.l6ia')
    hxf=out/(NAME+'.hxf')
    l6.write_bytes(arch)
    subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(l6)],cwd=ROOT,stdout=subprocess.DEVNULL,check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(l6),str(hxf),'--donor',str(donor)],cwd=ROOT,stdout=subprocess.DEVNULL,check=True)
    restored,was_hxf=pa.load_l6ia_from_any(str(hxf))
    assert was_hxf and restored==arch
    report={'variant':NAME,'hardware_tested':False,'donor_sha256':DONOR_SHA256,
            'modified_L6IA_entries':diffs,'other_13_entries_byte_identical':True,
            'RAM_only_no_firmware_writes':True,
            'HXF_SHA256':hashlib.sha256(hxf.read_bytes()).hexdigest(),
            'L6IA_SHA256':hashlib.sha256(arch).hexdigest(),
            'hxf_path':str(hxf),**report_m4,**report_sharc}
    (out/'manifest-build.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    print(json.dumps(build(),indent=2))
