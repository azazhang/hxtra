#!/usr/bin/env python3
"""R05 read-only native signal visibility audit against R03C TAP events.

Requests only existing native editor diagnostics: 0x13 (IOM4 event ledger)
and 0x50 (R03C TAP count). Neither edits a preset or changes the pedal.
Measures whether a source peak is published and reaches M4 packed bar state.
It cannot establish that every TAP event produced audible analog output or
that the physical LCD repainted: neither is measured by these commands.

Typical: python tools/io_level_r05_tap_peak_audit.py --samples 800 \
            --interval .02 --out /tmp/io-r05-HW04.jsonl
"""
import argparse
import json
import statistics
import time
from pathlib import Path

K_OUT1=('0x0002002a',1)
K_OUT2=('0x0002002a',2)
K_IN=('0x00020002',3)


def keyed(row,key):
    return next((e for e in row['native_records'] if
        (e['object_family'],e['parameter_id'])==key),None)


def summarize(rows,threshold=-30.0,bar_threshold=85):
    """Return conservative full-beat-window source vs packed-bar availability.

    Windows begin with observed TAP counter transitions and stop at the next
    transition. One final incomplete beat is excluded. This is a host proxy
    for on-device values, not a physical sound or optical measurement.
    """
    if len(rows)<2:
        raise ValueError('at least two rows required')
    changes=[i for i in range(1,len(rows)) if rows[i]['led_count']!=rows[i-1]['led_count']]
    windows=[]
    for a,b in zip(changes,changes[1:]):
        w=rows[a:b]
        peak1=max((x['output1_last'] for x in w if x['output1_last'] is not None),default=None)
        peak2=max((x['output2_last'] for x in w if x['output2_last'] is not None),default=None)
        peakbar=max(x['output_bar_pixels'] for x in w)
        windows.append({'tap_count':rows[a]['led_count'],'peak1':peak1,'peak2':peak2,
                        'bar_peak_pixels':peakbar,
                        'out1_detected':peak1 is not None and peak1>threshold,
                        'out2_detected':peak2 is not None and peak2>threshold,
                        'bar_detected':peakbar>bar_threshold,
                        'source1_new_records':w[-1]['output1_events']-w[0]['output1_events'],
                        'source2_new_records':w[-1]['output2_events']-w[0]['output2_events']})
    duration=rows[-1]['time_s']-rows[0]['time_s']
    result={'samples':len(rows),'duration_s':round(duration,4),'tap_counter_delta':rows[-1]['led_count']-rows[0]['led_count'],
            'complete_tap_intervals':len(windows),
            'output1_high_intervals':sum(x['out1_detected'] for x in windows),
            'output2_high_intervals':sum(x['out2_detected'] for x in windows),
            'either_output_key_high_intervals':sum(x['out1_detected'] or x['out2_detected'] for x in windows),
            'M4_packed_bar_high_intervals':sum(x['bar_detected'] for x in windows),
            'output1_event_rate_Hz':round((rows[-1]['output1_events']-rows[0]['output1_events'])/duration,3) if duration>0 else None,
            'output2_event_rate_Hz':round((rows[-1]['output2_events']-rows[0]['output2_events'])/duration,3) if duration>0 else None,
            'sample_interval_median_s':round(statistics.median(rows[i]['time_s']-rows[i-1]['time_s'] for i in range(1,len(rows))),4),
            'native_nonempty_packets_delta':rows[-1]['native_nonempty_packets']-rows[0]['native_nonempty_packets'],
            'bar_state_change_delta':rows[-1]['bar_state_changes']-rows[0]['bar_state_changes'],
            'all_M4_metronome_flags_active':all(x['metronome_transport_active'] for x in rows),
            'physical_sound_observed':False,'actual_LCD_paints_measured':False,'per_beat':windows}
    return result


def capture(samples,interval,out):
    import hx_ctl
    import io_level_r04_native_ledger as io
    import metro_led_r03c_probe as tap
    rows=[]
    start=time.monotonic()
    with hx_ctl.HxCtl(timeout=4) as ctl, out.open('w') as f:
        for i in range(samples):
            d=io.decode(ctl.ed.request(0x13,timeout=4))
            t=tap.decode(ctl.ed.request(0x50,timeout=4))
            assert t['revision']=='METRO-LEDSYNC-R03C-HWGLITCH-REPAIR', t['revision']
            a=keyed(d,K_OUT1)
            b=keyed(d,K_OUT2)
            c=keyed(d,K_IN)
            if a is None or b is None or c is None:
                raise RuntimeError('A required native key has not appeared yet; no evidence of its physical identity')
            row={'sample':i,'time_s':time.monotonic()-start,
                 'led_count':t['LED_on_count_low31'],
                 'metronome_transport_active':t['M4_Metronome_active_flag'],
                 'output1_last':a['last'],'output1_events':a['observations'],
                 'output2_last':b['last'],'output2_events':b['observations'],
                 'input_last':c['last'],
                 'output_bar_pixels':d['bulk_right_pixels'],'input_bar_pixels':d['bulk_left_pixels'],
                 'bar_state_changes':d['bulk_bar_state_changes'],
                 'native_nonempty_packets':d['native_nonempty_packets_seen']}
            f.write(json.dumps(row)+'\n')
            f.flush()
            rows.append(row)
            if i+1<samples:
                time.sleep(interval)
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--samples',type=int,default=320)
    p.add_argument('--interval',type=float,default=.02)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--threshold',type=float,default=-30)
    args=p.parse_args()
    if not 10<=args.samples<=5000 or not .01<=args.interval<=60:
        p.error('samples must be 10..5000 and interval .01..60s')
    rows=capture(args.samples,args.interval,args.out)
    print(json.dumps(summarize(rows,threshold=args.threshold),indent=2))

if __name__=='__main__':
    main()
