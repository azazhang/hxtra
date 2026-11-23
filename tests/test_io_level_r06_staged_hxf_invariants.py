"""Real R06 HXF + browser plan release-gate tests; no pedal operations.

Check only precise claims: original R06C non-M4 entries unchanged,
R01 M4 code differences limited to two newly chained callbacks,
and Chrome can stage nine RAM regions with two read-only base CRC checks.
"""
import hashlib,json,struct
from pathlib import Path

import l6ia,patch_amp as pa,patch_menu as pm
from build_io_level_r06_segmented_peak_envelope import NAME,FROZEN,FROZEN_SHA256
from build_io_level_r01_native_frame_probe import NAME as R01_NAME

ROOT=Path(__file__).parents[1]
OUT=ROOT/'build/browser-ramrun'/NAME
R01=ROOT/'build/browser-ramrun'/R01_NAME/(R01_NAME+'.hxf')
R06=OUT/(NAME+'.hxf')

def h(data):return hashlib.sha256(data).hexdigest()

def test_actual_packed_r05_hxf_matches_report_and_preserves_14_full_entries():
    manifest=json.loads((OUT/'manifest-build.json').read_text())
    donor=FROZEN.read_bytes()
    assert h(donor)==FROZEN_SHA256
    assert h(R06.read_bytes())==manifest['HXF_SHA256']
    assert manifest['modified_archive_entries']==[0]
    assert manifest['new_DSP_bootstream_bytes']==0
    assert manifest['new_SHARC_instructions']==0
    assert manifest['diagnostic_read_only'] is True
    assert manifest['native_rolling_USB_payload_bytes']==640
    assert manifest['native_keyed_event_slots']==24
    assert manifest['R06_16_LEDs_per_bar'] is True
    assert manifest['R06_native_interframe_peak_latch'] is True
    assert manifest['R06_peak_from_TAP_flag'] is False
    assert manifest['R06_IOM6_paint_telemetry_bytes']==32
    assert manifest['input_candidate_family_param']==['0x00020002',3]
    assert manifest['output_candidate_family_param']==['0x0002002a',1]
    base,_=pa.load_l6ia_from_any(str(FROZEN))
    r01,_=pa.load_l6ia_from_any(str(R01))
    r05,_=pa.load_l6ia_from_any(str(R06))
    assert len(l6ia.parse(base))==len(l6ia.parse(r01))==len(l6ia.parse(r05))==15
    assert [i for i in range(15) if pa.get_entry_swapped(base,i)!=pa.get_entry_swapped(r05,i)]==[0]
    for i in range(1,15):
        assert pa.get_entry_swapped(base,i)==pa.get_entry_swapped(r05,i)
    d0=pa.get_entry_swapped(r05,0)
    assert b'DSP Usage Display' in d0 and b'Breathing Line' in d0
    p0=pm.Patch(pa.get_entry_swapped(r01,0),[],{})
    p=pm.Patch(d0,[],{})
    for site in (0x28da6134,0x28d96e28,0x28d96adc):
        assert p0.read(site,4)!=p.read(site,4)
    assert manifest['R06_M4_app_size']-manifest['prior_R01_M4_app_size']==3024

def test_R06_browser_ram_plan_is_zero_eMMC_overlay_two_base_checks():
    manifest=json.loads((OUT/'manifest-stage.json').read_text())
    plan=json.loads((OUT/'regions/plan.json').read_text())
    spec=json.loads((OUT/'manifest-plan.json').read_text())
    assert manifest['hardware_boot_verified'] is False
    assert manifest['user_initiated_only'] is True
    assert manifest['new_SHARC_instructions']==0
    assert manifest['diagnostic_read_only'] is True
    assert manifest['R06_event_ledger_response_bytes']==640
    assert manifest['R06_event_ledger_slots']==24
    assert manifest['R06_led_segments_per_bar']==16
    assert manifest['R06_7px_LED_width_1px_gap'] is True
    assert manifest['R06_IOM6_signature']=='IOM6'
    assert manifest['R06_paint_callback_telemetry_available'] is True
    assert manifest['R06_physical_mapping_provisional'] is True
    assert manifest['R06_input_candidate']==['0x00020002',3]
    assert manifest['R06_output_candidate']==['0x0002002a',1]
    assert manifest['modified_L6IA_entries']==[0]
    assert manifest['writes']=='ram'
    assert manifest['eMMC_overlay_sectors']==0
    assert manifest['eMMC_readonly_checks']==2
    assert spec['plan_sha256']==h((OUT/'regions/plan.json').read_bytes())
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['changed']==[]
    assert plan['summary']['overlay_sectors']==plan['summary']['runs']==0
    assert len(plan['regions'])==9
    assert len(plan['checks'])==2
    assert plan['checks'][0][0]==0x8802 and plan['checks'][0][1]==1
    assert plan['checks'][1][0]==0x8803 and plan['checks'][1][1]==1023
    assert all((OUT/'regions'/r['file']).stat().st_size>0 for r in plan['regions'])
    html=(OUT/'index.html').read_text()
    for x in ('manifest.checks?.length!==2','manifest.summary?.overlay_sectors!==0',
              'manifest.summary?.changed?.length!==0','do not flash with',
              'physical jack'):
        assert x in html,x
    assert h((OUT/'ramrun.js').read_bytes())==manifest['browser_SHA256']
    assert h((OUT/'firmware-ramboot.dfu').read_bytes())==manifest['loader_SHA256']
