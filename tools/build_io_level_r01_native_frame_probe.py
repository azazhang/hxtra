#!/usr/bin/env python3
"""IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE: exact-R03C M4-only diagnostic overlay.

Uses the exact successfully flashed HXtra 1.2.1 / R03C image as donor;
adds one one-shot snapshot of stock SHARC->M4 incoming SPI frames and
registers a read-only editor command 0x4f to retrieve it. Neither DSP
instructions nor model lists nor presets/settings nor user features change.
Build is offline. This does not initiate a pedal RAM boot or flash.

This is a data-path discovery PROBE, not an audio meter or an HXF approved
for permanent flashing. Actual native input/output event byte offsets must
be observed and independently validated before building a visual level meter.
"""
from pathlib import Path
import hashlib,json,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/sharc')]
import patch_amp as pa,patch_menu as pm,l6ia,setting_ids

NAME='IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE'
FROZEN=ROOT/'build/browser-ramrun/METRO-LEDSYNC-R03C-HWGLITCH-REPAIR/METRO-LEDSYNC-R03C-HWGLITCH-REPAIR.hxf'
FROZEN_SHA256='42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b'
RX_LIT=0x28da6134
REG_CALL=0x28d96adc
FROZEN_GR_RX=0x28e55521
FROZEN_REG_WRAPPER=0x28e60f24
MOD='src/m4/io_level_r01_native_frame_probe.s'
CHANGED_SITES=(RX_LIT, REG_CALL)

def sha(data):return hashlib.sha256(data).hexdigest()

def patch(arch):
    before=lambda n:pa.get_entry_swapped(arch,n)
    original=before(0)
    p=pm.Patch(original,[],{},before)
    assert p.u32(RX_LIT)==FROZEN_GR_RX,'wrong frozen R03C GR frame receiver'
    sitebytes=p.read(REG_CALL,4)
    dest=setting_ids.bl_targets(struct.unpack('<2H',sitebytes),REG_CALL)[0]
    assert dest==FROZEN_REG_WRAPPER,'wrong exact R03C editor-command registration chain'
    assert pm.bl(REG_CALL,dest)==sitebytes
    module=p.module(MOD)
    p.chain_ptr(RX_LIT,FROZEN_GR_RX,before=module['io_probe_frame'])
    p.chain_bl(REG_CALL,dest,after=module['io_probe_register'])
    p.finish_chains()
    replaced=p.output()
    assert set(replaced)=={0},'unexpected SHARC firmware or UI assets modified'
    e0=replaced[0]
    offsets=[i for i,(a,b) in enumerate(zip(original,e0)) if a!=b]
    allowed=set(range(24))
    for site in CHANGED_SITES:
        start=p.off(site,4);allowed.update(range(start,start+4))
    for s in p.segs:allowed.update(range(s[0],s[0]+20))
    changed_unallowed=[i for i in offsets if i not in allowed and i<len(original)-8]
    assert not changed_unallowed,changed_unallowed[:20]
    for marker in (b'DSP Usage Display',b'Breathing Line',b'Main+Snd',b'Path A',b'FS1 Hold'):
        assert marker in e0,marker
    new,_,_=l6ia.rebuild_archive(arch,replaced)
    original_entries=l6ia.parse(arch);new_entries=l6ia.parse(new)
    assert len(original_entries)==len(new_entries)==15
    for i in range(1,15):
        assert before(i)==pa.get_entry_swapped(new,i),f'original Entry {i} changed'
    assert new_entries[2]['payload_len']==original_entries[2]['payload_len']==524212
    return new,{
        'base_R03C_HXF_SHA256':FROZEN_SHA256,
        'modified_archive_entries':[0],
        'all_14_other_entries_including_SHARC_entry2_unchanged':True,
        'R03C_original_M4_bytes_changed_only_at_RX_and_editor_registration':True,
        'changed_M4_hooks':[hex(x) for x in CHANGED_SITES],
        'original_RX_GR_hook':hex(FROZEN_GR_RX),
        'original_registration_chain':hex(FROZEN_REG_WRAPPER),
        'original_entry0_size':len(original),
        'new_entry0_size':len(e0),
        'module_source_SHA256':sha((ROOT/MOD).read_bytes()),
        'module_symbols':{k:hex(module[k]) for k in ('io_probe_frame','io_probe_register','io_probe_command')},
        'new_command':'0x4f read-only, return exactly 1040 bytes including 16-byte diagnostic header + 1024-byte raw RX frame',
        'new_SHARC_instructions':0,
        'new_DSP_bootstream_bytes':0,
        'writes_presets_settings_or_storage':False,
        'hardware_tested':False,
    }

def build(out=None):
    out=Path(out or ROOT/'build/browser-ramrun'/NAME)
    source=FROZEN.read_bytes()
    assert sha(source)==FROZEN_SHA256,'actual tested frozen R03C donor differs; abort'
    arc,was_hxf=pa.load_l6ia_from_any(str(FROZEN))
    assert was_hxf
    updated,report=patch(arc)
    out.mkdir(parents=True,exist_ok=True)
    l6=out/(NAME+'.l6ia')
    hxf=out/(NAME+'.hxf')
    l6.write_bytes(updated)
    subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(l6)],check=True,cwd=ROOT,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(l6),str(hxf),'--donor',str(FROZEN)],check=True,cwd=ROOT,stdout=subprocess.DEVNULL)
    decoded,ishxf=pa.load_l6ia_from_any(str(hxf))
    assert ishxf and decoded==updated
    report.update({'name':NAME,'hxf_path':str(hxf),'HXF_SHA256':sha(hxf.read_bytes()),
                   'L6IA_SHA256':sha(updated),'ram_only_probe_not_for_updater':True,
                   'active_pedal_untouched':True})
    (out/'manifest-build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report

if __name__=='__main__':build()
