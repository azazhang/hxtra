#!/bin/sh
# METRO-TAPSYNC-R02B3-BPM-RELOCK-DSPMETER: reconstructed installed HXtra v1.2.1 features.
# Restores donor-verified UI settings and model-browser titles omitted by R02B2.
# The optional HX_USB_MONITOR SHARC routing feature is excluded from this RAM
# experiment: with the new sync code, Entry 2 exceeded 512 KiB by 564 bytes.
# Preserve that limitation until the kernel or LDR stream can be reduced.
set -eu
cd "$(dirname "$0")/.."
: "${HX_STOCK_HXF:=$HOME/Downloads/HX_Stomp_v3.80.0_0x103966115.hxf}"
: "${HX_R02B3_OUT:=build/HXStomp380_HXtra121_METRO-TAPSYNC-R02B3-BPM-RELOCK-DSPMETER_RAM.hxf}"
export HX_NAM_SLOTS=1 HX_CLICK=1 HX_BPM=1 HX_GR=1 HX_FX_GATE=1 HX_GATE_SC=1
export HX_METRO_SPI_PHASE=1 HX_USB_INPUT=1 HX_SCREEN_MIRROR=1
# Installed donor's settings and display control hooks, omitted from R02B2:
export HX_LABEL_COLOR=1 HX_TUNER=1 HX_TAP_COLOR=1 HX_BREATHING_LINE=1
export HX_DSP_METER=1 HX_LONG_PRESS=1
unset HX_USB_MONITOR
export HX_PRESET_COLOR=1 HX_MORE_SNAPSHOTS=1 HX_CC_TAP=1 HX_REAL_NAMES=1
exec python3 build.py "$HX_STOCK_HXF" -o "$HX_R02B3_OUT" --no-check
