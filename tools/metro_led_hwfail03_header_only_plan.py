#!/usr/bin/env python3
"""SHARC-only HWFAIL03: change only the RAM overlay metadata vs failed HWFAIL02.

The HXF is deliberately byte-identical to the failed HWFAIL02 SHARC-only
image; this control adds an overlaid eMMC subheader sector 0x8802 containing
the new Entry2 CRC/length. That is the SINGLE experimental difference from
the failed SHARC-only boot. No M4 or other donor features are altered.
Offline generation only; physical RAM execution requires a separate user click.
"""
from pathlib import Path
import hashlib,sys
from metro_led_r02d_ramplan_header import make_plan
from metro_led_donor_patch import DONOR_SHA256

HWFAIL02_HXF_SHA256='3aa8d41b6d925272a00db2a16f2c112d1399f0adde70131ee3f78d47c09cf2ce'

def main():
    if len(sys.argv)!=4:raise SystemExit('usage: metro_led_hwfail03_header_only_plan.py DONOR FAILED_SHARC_ONLY.hxf OUTPUT_DIR')
    donor,candidate,out=sys.argv[1:]
    assert hashlib.sha256(Path(donor).read_bytes()).hexdigest()==DONOR_SHA256
    assert hashlib.sha256(Path(candidate).read_bytes()).hexdigest()==HWFAIL02_HXF_SHA256,'R02C SHARC program image must remain absolutely unchanged'
    result=make_plan(donor,candidate,out,expected_entry2_bytes=524284,
      variant='METRO-LEDSYNC-HWFAIL03-SHARC-ONLY-HEADER-OVERLAY')
    assert result['total_overlay_sectors']==12
    assert result['header_overlaid_at_emmc_sector']=='0x8802'
    assert result['original_entry2_bytes']==524212 and result['candidate_entry2_bytes']==524284
if __name__=='__main__':main()
