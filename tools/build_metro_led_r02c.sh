#!/bin/sh
# METRO-LEDSYNC-R02C-DONOR-EGRESS: exact installed HXtra v1.2.1, no feature rebuild.
set -eu
cd "$(dirname "$0")/.."
DONOR=${HX_V121_DONOR:-"$HOME/Downloads/HXtra_v1.2.1.hxf"}
TARGET=build/HXtra_v1.2.1_METRO-LEDSYNC-R02C-DONOR-EGRESS_RAM.hxf
ARCHIVE=build/METRO-LEDSYNC-R02C-DONOR-EGRESS-OFFLINE.l6ia
REGIONS=build/browser-ramrun/METRO-LEDSYNC-R02C-DONOR-EGRESS/regions
mkdir -p build "$REGIONS"
PYTHONPATH=tools:tools/sharc python3 tools/metro_led_sharc_patch.py "$DONOR" "$ARCHIVE"
python3 tools/l6ia_verify.py "$ARCHIVE" | tail -3
python3 tools/hxf.py pack "$ARCHIVE" "$TARGET" --donor "$DONOR"
PYTHONPATH=tools python3 tools/metro_led_r02c_ramplan.py plan "$TARGET" --stock "$DONOR" --out "$REGIONS"
shasum -a 256 "$DONOR" "$TARGET" "$REGIONS/plan.json"
