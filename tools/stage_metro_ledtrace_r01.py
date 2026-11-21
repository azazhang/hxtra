#!/usr/bin/env python3
"""Generate a versioned, user-initiated WebUSB page for M4LEDTRACE-R01.

Copies upstream-proven RAM loader bytes unchanged; no browser launch, no USB I/O.
"""
from pathlib import Path
import hashlib,json,shutil,sys
from build_metro_ledtrace_r01 import ROOT,NAME

def main():
    b=ROOT/'build/browser-ramrun'/NAME
    assert b.is_dir()
    manifest=json.loads((b/'manifest.json').read_text())
    plan=json.loads((b/'regions/plan.json').read_text())
    assert manifest['variant']==NAME
    assert manifest['hardware_run_initiated'] is False
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['overlay_sectors']==0
    assert plan['summary']['changed']==[]
    assert len(plan['regions'])==9 and len(plan['checks'])==1
    donor=ROOT/'web/experiments/metro-donor-v121-unchanged-control'
    dst=ROOT/'web/experiments/metro-ledsync-m4ledtrace-r01'
    dst.mkdir(parents=True,exist_ok=True)
    js=(donor/'ramrun.js').read_bytes()
    assert js== (ROOT/'web/experiments/metro-ledsync-hwfail03-sharc-header-only/ramrun.js').read_bytes()
    (dst/'ramrun.js').write_bytes(js)
    # Reuse the existing WebUSB implementation unchanged.
    html=(donor/'index.html').read_text()
    old='METRO-DONOR-V121-UNCHANGED-RAM-CONTROL'
    assert html.count(old)>=5
    html=html.replace(old,NAME)
    start=html.index('<p><strong>Startup isolation positive control:')
    end=html.index('<div id="status">')
    html=html[:start]+'''<p><strong>Read-only M4 LED timing diagnostic — not an audio-sync fix.</strong>
This test runs the exact installed HXtra v1.2.1 firmware with just two M4 hook sites changed:
post-filter FS3 LED sender and USB diagnostic registration. The SHARC audio program,
all other non-M4 firmware entries, preset models, Global Settings, DSP Usage Display,
and USB Monitor are preserved. The original donor SHA256 is
<code>96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0</code>.</p>
<p>The M4 uses the built-in 1-microsecond timebase to store the last 16 actual
LED-control ON/OFF transitions after HXtra's visibility filter.
Read the data with <code>tools/metro_ledtrace_r01_probe.py</code> after the pedal
has booted. The test does not change metronome sound or attempt synchronization.</p>
<p class="warn"><strong>Experimental RAM load: user-initiated only.</strong>
Nine RAM regions, zero SHARC/eMMC overlay sectors, and RAM-only writes. The
reference eMMC read-only CRC will be attempted if the loader can access eMMC;
prior HXtra RAM tests reported status 0x10b and skipped that check. RAM transfer
completion alone does not prove the firmware is running. Verify the LCD and
USB editor. If the pedal freezes, power cycle to restore installed HXtra.</p>
''' + html[end:]
    html=html.replace("if(manifest.regions?.length!==9||manifest.checks?.length!==1||manifest.summary?.writes!=='ram')",
    "if(manifest.regions?.length!==9||manifest.checks?.length!==1||manifest.summary?.writes!=='ram'||manifest.summary?.overlay_sectors!==0||manifest.summary?.changed?.length!==0)")
    html=html.replace("Unmodified HXtra v1.2.1 running","M4LEDTRACE RAM handoff reported")
    html=html.replace("unchanged installed v1.2.1 startup control","original SHARC preserved, read-only LED microsecond trace")
    html=html.replace("SUCCESS: WebUSB reported RAM-run completion.","WebUSB RAM handoff reported; confirm pedal UI/editor before accepting hardware boot.")
    # Validate obsolete instructions were removed, making the page unambiguous.
    assert 'Only run once after power cycling R02C' not in html
    assert 'unchanged installed HXtra v1.2.1 firmware' not in html
    assert 'overlay_sectors!==0' in html
    assert 'Unmodified HXtra v1.2.1 running' not in html
    (dst/'index.html').write_text(html)
    (dst/'README.md').write_text(f"""# {NAME}

M4-only **unproven physical** diagnostic, built from exact installed donor.
Run no automatic firmware loads. The WebUSB loader only uploads SDRAM
regions; the user controls starting and selecting the pedal in Chrome.
The SHARC Entry2 and all 13 other non-M4 entries remain identical
to donor. This only traces visible FS3 LED-control ON/OFF transitions
with microsecond timer 0x28da6458, readable via USB 0x50.

- Project build: `tools/build_metro_ledtrace_r01.py`
- Test: `tests/test_metro_ledtrace_r01.py`
- Decoder: `tools/metro_ledtrace_r01_probe.py`
- Offline binary: `build/browser-ramrun/{NAME}/{NAME}.hxf`
- RAM plan: `build/browser-ramrun/{NAME}/regions/plan.json`
- eMMC application writes: none
- eMMC overlay sectors: 0
- Upstream WebUSB `ramrun.js`: same SHA256 as donor control
- Hardware boot and real optical/audio phase: untested
""")
    src=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/firmware-ramboot.dfu'
    assert src.exists() and src.stat().st_size==4112
    shutil.copyfile(src,b/'firmware-ramboot.dfu')
    shutil.copyfile(dst/'ramrun.js',b/'ramrun.js')
    shutil.copyfile(dst/'index.html',b/'index.html')
    info={'web_variant':NAME,'html_sha256':hashlib.sha256((b/'index.html').read_bytes()).hexdigest(),
          'unchanged_webusb_sha256':hashlib.sha256(js).hexdigest(),
          'loader_sha256':hashlib.sha256((b/'firmware-ramboot.dfu').read_bytes()).hexdigest(),
          'plan_sha256':manifest['plan_sha256'],'hardware_run_started':False}
    print(json.dumps(info,indent=2))
if __name__=='__main__':main()
