#!/usr/bin/env python3
"""R03C HWGOOD01: reproducible real-HX-Stomp M4 LED→first TX callback timing.

Exactly one observation per event count, because USB poll rate is higher
than 100-BPM LED repetition. 0x50 telemetry reports internal M4 1us clock,
not photon timestamp, SPI transfer completion, DSP reception or audible
click onset. Preserve that boundary in any report or chart.
"""
from pathlib import Path
import argparse,hashlib,json,statistics
ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'tests/hardware_evidence/METRO-LEDSYNC-R03C-HWGOOD01-LED-TO-M4TX-80SAMPLES-20261120.jsonl'
TARGET=ROOT/'tests/hardware_evidence/METRO-LEDSYNC-R03C-HWGOOD01-LEDTX-TIMING-ANALYSIS-20261120.json'
def percent(a,p):
    a=sorted(a)
    if not a:return None
    z=p*(len(a)-1)
    lo=int(z)
    t=z-lo
    return a[lo]*(1-t)+a[min(lo+1,len(a)-1)]*t
def analyze(src=DEFAULT):
    src=Path(src)
    rows=[json.loads(t) for t in src.read_text().splitlines() if t.strip()]
    assert rows and all(r['revision']=='METRO-LEDSYNC-R03C-HWGLITCH-REPAIR' for r in rows)
    assert [r['sample'] for r in rows]==list(range(len(rows)))
    seen={}
    for r in rows:
        if r['M4_latency_measure_valid'] and r['last_M4_TX_event_is_current']:
            seen.setdefault(r['raw_LED_event_count'],r)
    ids=list(seen)
    events=list(seen.values())
    assert ids==list(range(ids[0],ids[-1]+1)), 'missed event in the sampled counter range'
    delays=[r['last_M4_LED_request_to_first_SPI_TX_us'] for r in events]
    stamps=[r['last_accepted_M4_LED_on_timestamp_us_u32'] for r in events]
    intervals=[(b-a)&0xffffffff for a,b in zip(stamps,stamps[1:])]
    for r in rows:
        assert r['last_M4_TX_pair_is_valid'] and r['last_M4_TX_event_is_current']
    invariant_fields=('SPI_tx_frames_skipped','SPI_tx_frames_no_TAP_or_LED_hidden',
       'noTAP_frames_held_through_grace','noTAP_frames_sent_as_explicit_local_fallback',
       'short_dark_reversals_filtered','slot8_Metronome_engage_transitions')
    out={
      'variant':'METRO-LEDSYNC-R03C-HWGLITCH-REPAIR',
      'hardware_test':'HWGOOD01',
      'firmware_hxf_sha256':'42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b',
      'source_jsonl':str(src.relative_to(ROOT)) if src.is_relative_to(ROOT) else str(src),
      'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
      'distinct_hardware_led_event_count':len(events),
      'raw_readonly_USB_0x50_samples':len(rows),
      'host_monotonic_observation_span_seconds':rows[-1]['host_monotonic_s']-rows[0]['host_monotonic_s'],
      'first_event_raw_u32':ids[0],
      'last_event_raw_u32':ids[-1],
      'all_reported_M4_TX_pairs_consistent':True,
      'all_reported_M4_TX_counts_current':True,
      'M4_LED_command_to_first_M4_SPI_TX_callback_us':{
          'per_distinct_event':delays,
          'min':min(delays),
          'median':statistics.median(delays),
          'mean':statistics.mean(delays),
          'population_std':statistics.pstdev(delays),
          'p05_linear_interpolated':percent(delays,.05),
          'p95_linear_interpolated':percent(delays,.95),
          'max':max(delays),
          'count':len(delays),
      },
      'M4_postfilter_LED_ON_to_ON_intervals_us':{
          'values':intervals,
          'count':len(intervals),
          'median_us':statistics.median(intervals),
          'median_equivalent_BPM':60e6/statistics.median(intervals),
          'min':min(intervals),'max':max(intervals)
      },
      'cumulative_interruptions_during_query':{
        k:{'first':rows[0][k],'last':rows[-1][k], 'increase':rows[-1][k]-rows[0][k]}
        for k in invariant_fields},
      'timing_origin':'M4 internal post-filter FS3 LED driver request, BEFORE optical LED',
      'timing_destination':'FIRST M4 SPI TX callback stamp with the event, BEFORE actual SPI physical transfer and SHARC consumption',
      'physical_acoustic_click_latency_measured':False,
      'optical_LED_latency_measured':False,
      'audio_USB_capture_result':'all 8 HX Stomp and all 10 FLOW 8 input channels returned zero; no acoustic onset available',
      'user_hardware_report':'R03C duplicate clicking resolved, requested major working version; perceptible optical-audio lag remains to be measured',
    }
    return out
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--jsonl',type=Path,default=DEFAULT)
    parser.add_argument('--output',type=Path,default=TARGET)
    a=parser.parse_args()
    result=analyze(a.jsonl)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    show=result['M4_LED_command_to_first_M4_SPI_TX_callback_us']
    print(json.dumps({'saved':str(a.output),'unique_led_events':show['count'],'mean_us':show['mean'],'median_us':show['median'],'min_us':show['min'],'max_us':show['max'],'p95_us':show['p95_linear_interpolated']},indent=2))
