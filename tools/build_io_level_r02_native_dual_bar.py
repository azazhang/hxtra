#!/usr/bin/env python3
"""IO-LEVEL-R02: live two-bar M4 prototype on the exact flashed R03C HXF.

R02 extends the offline-validated, physically booted R01 M4 receive-frame
instrument with a native-packet subscriber and two horizontal Home bars.
Neither the SHARC image, bootloader, GR/DSP Usage/Breathing/USB Monitor nor
the installed R03C metronome source is modified.

This is a *RAM-only experiment*; the assignment of first/last native meter
record pairs to physical Input/Output is still to be tested with an actual
instrument signal. We do not claim a finished calibrated meter or safe
persistent firmware release. Absolutely no device access in this script.
"""
from pathlib import Path
import hashlib,json,subprocess,sys,struct
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/sharc')]
import patch_amp as pa,patch_menu as pm,l6ia
from build_io_level_r01_native_frame_probe import (
    patch as patch_r01, FROZEN, FROZEN_SHA256,
)
NAME='IO-LEVEL-R02-NATIVE-DUAL-BAR-PROTOTYPE'
R01_IMAGE_SHA256='1ea5799abbadc826253d4e7866ebc28d7003b9f89403640f6f7c1fa2353f0e86'
MOD='src/m4/io_level_r02_native_dual_bar.s'
RX_PTR=0x28da6134
HOME_PAINT_PTR=0x28d96e28
ORIGINAL_R03C_GR_HOME=0x28e55451
PATCH_SITES=(RX_PTR,HOME_PAINT_PTR)

def sha(data):return hashlib.sha256(data).hexdigest()

def patch(arch):
    donor=lambda i:pa.get_entry_swapped(arch,i)
    r01,base_report=patch_r01(arch)
    installed_r01=ROOT/'build/browser-ramrun/IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE/IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE.hxf'
    assert sha(installed_r01.read_bytes())==R01_IMAGE_SHA256
    installed_archive,was_hxf=pa.load_l6ia_from_any(str(installed_r01))
    assert was_hxf and installed_archive==r01, 'R01 module mismatch versus physically booted R01'
    baseline=lambda i:pa.get_entry_swapped(r01,i)
    e0=baseline(0)
    p=pm.Patch(e0,[],{},baseline)
    old_rx=p.u32(RX_PTR)
    old_home=p.u32(HOME_PAINT_PTR)
    assert old_rx&1 and old_rx!=0x28e55521, 'R01 snapshot wrapper missing'
    assert old_home==ORIGINAL_R03C_GR_HOME, 'Home GR/breathing chain unexpectedly changed'
    mod=p.module(MOD)
    p.chain_ptr(RX_PTR,old_rx,before=mod['io_meter_frame'])
    p.chain_ptr(HOME_PAINT_PTR,old_home,after=mod['io_meter_draw'])
    p.finish_chains()
    repl=p.output()
    assert set(repl)=={0}
    new_e0=repl[0]
    changed=[i for i,(a,b) in enumerate(zip(e0,new_e0)) if a!=b]
    allowed=set(range(24))
    for site in PATCH_SITES:
        x=p.off(site,4);allowed.update(range(x,x+4))
    for seg in p.segs:
        allowed.update(range(seg[0],seg[0]+20))
    disallowed=[x for x in changed if x not in allowed and x<len(e0)-8]
    assert not disallowed,('unexpected changed R01 M4 bytes',disallowed[:15])
    for marker in (b'DSP Usage Display',b'Breathing Line',b'Main+Snd',b'Path A',b'FS1 Hold'):
        assert marker in new_e0,marker
    new,_,_=l6ia.rebuild_archive(r01,repl)
    assert len(l6ia.parse(new))==15
    for k in range(1,15):
        assert pa.get_entry_swapped(new,k)==donor(k),f'original Entry{k} modified'
    return new,{
      'variant':NAME,
      'donor_exact_flashed_R03C_SHA256':FROZEN_SHA256,
      'r01_hardware_booted_image_SHA256':R01_IMAGE_SHA256,
      'modified_archive_entries':[0],
      'original_14_non_M4_entries_identical':True,
      'new_SHARC_instructions':0,
      'new_DSP_bootstream_bytes':0,
      'prior_R01_M4_bytes_modified_only_at_two_new_hook_sites':True,
      'new_R02_M4_hook_pointers':[hex(x) for x in PATCH_SITES],
      'prior_R01_RX_callback':hex(old_rx),
      'prior_R03C_GR_Home_paint_callback':hex(old_home),
      'prior_R01_M4_app_size':len(e0),
      'R02_M4_app_size':len(new_e0),
      'R02_added_M4_app_bytes':len(new_e0)-len(e0),
      'source_module_sha256':sha((ROOT/MOD).read_bytes()),
      'module_entries':{k:hex(mod[k]) for k in
         ('io_meter_frame','io_meter_draw','io_level_to_bin','io_bar_state')},
      'native_packet_length_words':44,
      'measured_native_event_group_shape':'0x00020000 records 2,5 / 3,6 / 4,6 / 1,5 from HW02',
      'left_meter_source':'first native pair, channels 2 and 5',
      'right_meter_source':'last native pair, channels 1 and 5',
      'actual_input_output_channel_mapping_verified':False,
      'audio_input_output_calibrated_on_unit':False,
      'UI_horizontal_bar_locations':{'left':[24,113,132,5],
                                    'right':[164,113,132,5]},
      'UI_10bins_dbFS_edges':[-90,-72,-60,-48,-36,-24,-18,-12,-6,-3],
      'user_initiated_ram_only':True,
      'hardware_tested':False,
    }

def build(out=None):
    out=Path(out or ROOT/'build/browser-ramrun'/NAME)
    frozen=FROZEN.read_bytes()
    assert sha(frozen)==FROZEN_SHA256
    arch,hxf=pa.load_l6ia_from_any(str(FROZEN))
    assert hxf
    new,report=patch(arch)
    out.mkdir(parents=True,exist_ok=True)
    l6=out/(NAME+'.l6ia')
    h=out/(NAME+'.hxf')
    l6.write_bytes(new)
    subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(l6)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(l6),str(h),'--donor',str(FROZEN)],
                   cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    got,was=pa.load_l6ia_from_any(str(h))
    assert was and got==new
    report.update({'hxf_path':str(h),'HXF_SHA256':sha(h.read_bytes()),
      'L6IA_SHA256':sha(new),'R02_not_updater_flash_approved':True,
      'no_pedal_hardware_action':True})
    (out/'manifest-build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report

if __name__=='__main__':build()
