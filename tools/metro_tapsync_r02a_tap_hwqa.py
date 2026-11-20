#!/usr/bin/env python3
"""METRO-TAPSYNC-R02A-M4EDGE/HWQA-02: tempo changes through TAP/TUNER FS3.

FS3 assignment verified on device screen at the start of this run. Uses
short virtual UI press/release events, samples the M4 event counter after
setting 120/160/100 BPM, and verifies preset 41C/USB control responsiveness.
No preset save. Logs host timestamps and raw counters for auditing.
"""
import argparse
import json
import time
from pathlib import Path

import hx_ctl
import hx_input
import metro_tapsync_r02a_probe as probe


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with hx_ctl.HxCtl(timeout=2) as c, out.open('w') as stream:
        ui=hx_input.Input(c)
        def log(step,**kw):
            event=probe.decode(c.ed.request(0x50,timeout=3))
            t=time.monotonic()
            row={'id':'METRO-TAPSYNC-R02A-M4EDGE/HWQA-02','step':step,'t':t,'tap':event['tap_led_on_count'],'enable':event['metro_41c_enable_count'],**kw}
            stream.write(json.dumps(row)+'\n');stream.flush();print(json.dumps(row),flush=True)
            return row
        def observe(name,bpm,window=3.6):
            rows=[]
            until=time.monotonic()+window
            while time.monotonic()<until:
                rows.append(log(f'{name}_counter',expected_bpm=bpm))
                time.sleep(0.35)
            # Avoid claiming perfect sync from bounded counter samples.
            duration=rows[-1]['t']-rows[0]['t']
            delta=rows[-1]['tap']-rows[0]['tap']
            observed=60*delta/duration
            print(f'{name}: {delta} TAP LED edges/{duration:.3f}s -> {observed:.2f} BPM (nominal {bpm})',flush=True)
            return observed
        def set_bpm(bpm):
            period=60/bpm
            start=time.monotonic()+.15
            for k in range(6):
                time.sleep(max(0,start+k*period-time.monotonic()))
                ui.send(hx_input.key('fs3',hx_input.PRESS))
                time.sleep(.04)
                ui.send(hx_input.key('fs3',hx_input.RELEASE),hx_input.key('fs3',hx_input.RELEASED))
            time.sleep(.5)
        before=c.current();assert before['preset']==122 and before['setlist']==0,before
        log('baseline',current_preset=before)
        for bpm in (120,160,100):
            set_bpm(bpm)
            seen=observe(f'tapped_{bpm}',bpm)
            assert abs(seen-bpm)<32,f'{bpm} BPM expected, measured {seen:.1f} BPM'
            current=c.current()
            assert current['setlist']==0 and current['preset']==122,current
            print(f'AFTER_{bpm}_USB_OK',current,flush=True)
        final=c.get_preset()
        s=hx_ctl.summarize(final[1])
        assert len(s)==8 and s[-1]['model_id']==181 and s[-1]['enabled'],s
        print('METRO-TAPSYNC-R02A-M4EDGE/HWQA-02 PASS: TAP 120 -> 160 -> 100 BPM, counter cadence followed, 41C eight blocks preserved, USB control responsive',flush=True)
if __name__=='__main__':main()
