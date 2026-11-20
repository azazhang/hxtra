#!/usr/bin/env python3
"""METRO-TAPSYNC-R02A-M4EDGE/HWQA-01: repeat bypass & tempo Time knob.

Uses HXtra's established virtual UI controls. Preset 41C with the Metronome
selected (path A slot 7) is a strict precondition. Does not save the preset.
Writes a JSONL evidence stream and checks editor responsiveness throughout.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import hx_ctl
import hx_input
import metro_tapsync_r02a_probe as probe


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    with hx_ctl.HxCtl(timeout=2) as ctl, target.open('w') as f:
        io=hx_input.Input(ctl)
        initial=None

        def snap(label, metadata=None):
            nonlocal initial
            c=ctl.current()
            if c['preset']!=122 or c['setlist']!=0:
                raise RuntimeError(f'Wrong preset for R02A diagnostic: {c}')
            _, preset=ctl.get_preset()
            blocks=hx_ctl.summarize(preset)
            if len(blocks)!=8 or any(b['slot']!=j for j,b in enumerate(blocks)):
                raise RuntimeError('R02A 41C model grid changed unexpectedly')
            m=[b for b in blocks if b['model_id']==181]
            if len(m)!=1 or m[0]['slot']!=7:
                raise RuntimeError(f'Wrong selected metronome slot: {m}')
            ctr=probe.decode(ctl.ed.request(0x50,timeout=3))
            row={"id":"METRO-TAPSYNC-R02A-M4EDGE/HWQA-01","step":label,"time":time.time(),"tap":ctr['tap_led_on_count'],"enable":ctr['metro_41c_enable_count'],"metro_on":m[0]['enabled'],"metro_params":m[0]['params'],"blocks":len(blocks),"models":[b['model_id'] for b in blocks]}
            if metadata:row.update(metadata)
            f.write(json.dumps(row)+'\n');f.flush()
            print(json.dumps(row),flush=True)
            return row

        b=snap('baseline');initial=b['metro_params']
        assert b['metro_on'], 'Start with metronome selected and enabled'
        prev=b
        for n in range(1,5):
            io.press('knob4')
            time.sleep(.2)
            off=snap(f'cycle{n}_bypassed')
            assert not off['metro_on'] and off['enable']==prev['enable'],('off',off,prev)
            io.press('knob4')
            time.sleep(.2)
            on=snap(f'cycle{n}_reenabled')
            assert on['metro_on'] and on['enable']==off['enable']+1,('on',on,off)
            prev=on
        for n,delta in enumerate((1,-1,3,-3,5,-5),1):
            io.turn('knob1',delta)
            time.sleep(.25)
            row=snap(f'time_parameter_turn_{n}',{'knob1_clicks':delta})
            assert row['metro_on'] and row['enable']==prev['enable']
            prev=row
        final=snap('final')
        assert final['metro_params']==initial, ('Tempo knob return did not restore original params',initial,final['metro_params'])
        print('METRO-TAPSYNC-R02A-M4EDGE/HWQA-01 PASS: 4 bypass/resume cycles; 6 tempo knob changes; 8 model slots retained; no USB stall; final params restored',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as e:
        print('METRO-TAPSYNC-R02A-M4EDGE/HWQA-01 FAIL:',repr(e),file=sys.stderr,flush=True)
        raise
