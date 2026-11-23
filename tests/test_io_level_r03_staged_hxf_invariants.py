"""Real R03 HXF + browser plan release-gate tests; no pedal operations.

Check only precise claims: original R03C non-M4 entries unchanged,
R01 M4 code differences limited to two newly chained callbacks,
and Chrome can stage nine RAM regions with two read-only base CRC checks.
"""
import hashlib,json,struct
from pathlib import Path

import l6ia,patch_amp as pa,patch_menu as pm
from build_io_level_r03_native_rolling_meter import NAME,FROZEN,FROZEN_SHA256
from build_io_level_r01_native_frame_probe import NAME as R01_NAME

ROOT=Path(__file__).parents[1]
OUT=ROOT/'build/browser-ramrun'/NAME
R01=ROOT/'build/browser-ramrun'/R01_NAME/(R01_NAME+'.hxf')
R03=OUT/(NAME+'.hxf')

def h(data):return hashlib.sha256(data).hexdigest()

def test_actual_packed_r03_hxf_matches_report_and_preserves_14_full_entries():
    manifest=json.loads((OUT/'manifest-build.json').read_text())
    donor=FROZEN.read_bytes()
    assert h(donor)==FROZEN_SHA256
    assert h(R03.read_bytes())==manifest['HXF_SHA256']
    assert manifest['modified_archive_entries']==[0]
    assert manifest['new_DSP_bootstream_bytes']==0
    assert manifest['new_SHARC_instructions']==0
    assert manifest['diagnostic_read_only'] is True
    base,_=pa.load_l6ia_from_any(str(FROZEN))
    r01,_=pa.load_l6ia_from_any(str(R01))
    r03,_=pa.load_l6ia_from_any(str(R03))
    assert len(l6ia.parse(base))==len(l6ia.parse(r01))==len(l6ia.parse(r03))==15
    assert [i for i in range(15) if pa.get_entry_swapped(base,i)!=pa.get_entry_swapped(r03,i)]==[0]
    for i in range(1,15):
        assert pa.get_entry_swapped(base,i)==pa.get_entry_swapped(r03,i)
    d0=pa.get_entry_swapped(r03,0)
    assert b'DSP Usage Display' in d0 and b'Breathing Line' in d0
    p0=pm.Patch(pa.get_entry_swapped(r01,0),[],{})
    p=pm.Patch(d0,[],{})
    for site in (0x28da6134,0x28d96e28,0x28d96adc):
        assert p0.read(site,4)!=p.read(site,4)
    assert manifest['R03_M4_app_size']-manifest['prior_R01_M4_app_size']==960

def test_R03_browser_ram_plan_is_zero_eMMC_overlay_two_base_checks():
    manifest=json.loads((OUT/'manifest-stage.json').read_text())
    plan=json.loads((OUT/'regions/plan.json').read_text())
    spec=json.loads((OUT/'manifest-plan.json').read_text())
    assert manifest['hardware_boot_verified'] is False
    assert manifest['user_initiated_only'] is True
    assert manifest['new_SHARC_instructions']==0
    assert manifest['diagnostic_read_only'] is True
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
              'manifest.summary?.changed?.length!==0','Do not flash with',
              'Physical Input/Output assignment remains to be validated'):
        assert x in html,x
    assert h((OUT/'ramrun.js').read_bytes())==manifest['browser_SHA256']
    assert h((OUT/'firmware-ramboot.dfu').read_bytes())==manifest['loader_SHA256']
