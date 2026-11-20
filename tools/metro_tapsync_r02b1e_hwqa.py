#!/usr/bin/env python3
"""METRO-TAPSYNC-R02B1E-EVENT-ECHO/HWQA01: live end-to-end event counter/CRC validation.

Tests the dynamic R02B1E echo; restores the original 41C eight-block edit
buffer state, leaving the metronome bypassed, without saving to persistent preset.
"""
import argparse,json,time,sys
from pathlib import Path
import hx_ctl,hx_input
import metro_tapsync_r02b1e_probe as probe


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',required=True)
    ap.add_argument('--baseline',required=True)
    a=ap.parse_args()
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    original=json.loads(Path(a.baseline).read_text())
    with hx_ctl.HxCtl(timeout=2.5) as c, target.open('w') as stream:
        inp=hx_input.Input(c)
        def snap(label,**kwargs):
            current=c.current()
            if current['setlist']!=0 or current['preset']!=122:raise RuntimeError(f'Preset changed: {current}')
            _,p=c.get_preset()
            s=hx_ctl.summarize(p)
            if len(s)!=8 or [x['model_id'] for x in s]!=[x['model_id'] for x in original['blocks']]:
                raise RuntimeError('Preset model layout differs from baseline')
            ctr=probe.decode(c.ed.request(0x50,timeout=3))
            if ctr['dsp_echo_marker']!='0x4d543242' or not ctr['dsp_echo_integrity_valid']:
                raise RuntimeError(f'SHARC event echo or checksum failed: {ctr}')
            if ctr['dsp_echo_valid_frames']==0:
                raise RuntimeError(f'No verified dynamic SHARC return frames: {ctr}')
            tap_lag=ctr['tap_count_difference_m4_minus_dsp']
            enable_lag=ctr['enable_count_difference_m4_minus_dsp']
            # The USB read samples two tasks asynchronously. A beat may cross
            # between the M4 counter and SHARC echo snapshot; allow ±2 beats.
            if min(tap_lag,(1<<32)-tap_lag)>2:
                raise RuntimeError(f'Unexpected large M4-to-SHARC TAP lag: {ctr}')
            if enable_lag!=0:
                raise RuntimeError(f'Enable counter did not reach SHARC: {ctr}')
            row={'id':'METRO-TAPSYNC-R02B1E-EVENT-ECHO/HWQA01','step':label,'timestamp':time.time(),**ctr,'metro_enabled':s[7]['enabled'],'metro_params':s[7]['params'],**kwargs}
            stream.write(json.dumps(row)+'\n');stream.flush()
            print(json.dumps(row),flush=True)
            return row
        b=snap('baseline')
        if b['metro_enabled']:raise RuntimeError('Metronome initially enabled; expected 41C bypassed')
        prev=b
        try:
            for i in range(4):
                inp.press('knob4')
                time.sleep(.20)
                on=snap(f'enable_{i+1}')
                assert on['metro_enabled'] and on['metro_41c_enable_count']==prev['metro_41c_enable_count']+1
                inp.press('knob4')
                time.sleep(.20)
                off=snap(f'bypass_{i+1}')
                assert not off['metro_enabled'] and off['metro_41c_enable_count']==on['metro_41c_enable_count']
                prev=off
            # The physical knob 1 on this screen edits Time. Test via established HXtra USB input.
            for i,delta in enumerate([1,-1,3,-3,5,-5],1):
                inp.turn('knob1',delta)
                time.sleep(.20)
                s=snap(f'time_knob_{i}',steps=delta)
                assert not s['metro_enabled']
            s=snap('knob_restored')
            assert s['metro_params']==b['metro_params'],('knob failed restore',s['metro_params'],b['metro_params'])
            # FS3 TAP/TUNER assigned on Home screen, as observed in R02A; send 5 presses at 150 BPM.
            inp.press('view')
            time.sleep(.30)
            for j in range(5):
                inp.send(hx_input.key('fs3',hx_input.PRESS))
                time.sleep(.04)
                inp.send(hx_input.key('fs3',hx_input.RELEASE),hx_input.key('fs3',hx_input.RELEASED))
                if j<4:time.sleep(.36)
            time.sleep(1.0)
            snap('tap_150_after_5_presses')
            # Stay in Home mode so FS3 retains its TAP/TUNER assignment.
            # tempo restore to 100 BPM as in R02A test (six short TAP presses)
            for j in range(6):
                inp.send(hx_input.key('fs3',hx_input.PRESS))
                time.sleep(.04)
                inp.send(hx_input.key('fs3',hx_input.RELEASE),hx_input.key('fs3',hx_input.RELEASED))
                if j<5:time.sleep(.56)
            snap('tap_100_restored')
            inp.press('view')   # restore Edit view with the selected Metronome
        finally:
            # Read the live edit buffer before leaving; correct bypass if necessary.
            _,p=c.get_preset()
            ss=hx_ctl.summarize(p)
            if ss[7]['enabled']:
                inp.press('view')
                inp.press('knob4')
                time.sleep(.2)
            _,p=c.get_preset()
            ss=hx_ctl.summarize(p)
            before={(x['path'],x['slot']):x for x in original['blocks']}
            after={(x['path'],x['slot']):x for x in ss}
            unchanged=set(before)==set(after) and all((before[k]['model_id'],before[k]['enabled'],before[k]['params'])==(after[k]['model_id'],after[k]['enabled'],after[k]['params']) for k in before)
            print('FINAL_BUFFER_IDENTICAL',unchanged,'METRO_ENABLED',ss[7]['enabled'],flush=True)
            if not unchanged:raise AssertionError('41C edit buffer differs from backup')
            snap('final')
        print('METRO-TAPSYNC-R02B1E-EVENT-ECHO/HWQA01 PASS',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('METRO-TAPSYNC-R02B1E-EVENT-ECHO/HWQA01 FAIL',repr(e),file=sys.stderr,flush=True)
        raise
