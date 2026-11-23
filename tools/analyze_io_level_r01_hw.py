#!/usr/bin/env python3
"""Analyze R01 captured *actual* SPI payloads. No HX Stomp USB access.

Usage:
 python3 tools/analyze_io_level_r01_hw.py /tmp/io-level-r01-hw02-500.jsonl
 python3 tools/analyze_io_level_r01_hw.py ... --out /tmp/summary.json

Only index 2..(2 + payload word count) is new native message data.
Words beyond are leftover from previous DMA buffer use and must never
be presented as new meter readings. Values are labeled by raw family,
channel index and event order. Mapping to physical Input/Output is not
asserted until separately measured or traced.
"""
from __future__ import annotations
import argparse,collections,json,statistics
from pathlib import Path
from io_level_native_protocol import parse_frame

def analyze(rows):
    bylen=collections.Counter()
    byfamily=collections.Counter()
    bychannel=collections.Counter()
    byposition=collections.defaultdict(list)
    examples=[]
    nonempty=0
    invalid=[]
    complete_peak_packets=[]
    unclassified=0
    gr_count=0
    for row in rows:
        words=row['words_M4_raw_halfword_swapped']
        raw=parse_frame(words)
        if words[0]!=0xf00dface or words[255]!=0xecafd00f:
            invalid.append((row['sample'],'invalid raw M4 SPI framing'))
        if words[200]==0xf00d600d:gr_count+=1
        bylen[raw['native_payload_words']]+=1
        if not raw['native_payload_nonempty']:continue
        nonempty+=1
        if not raw['native_envelope_verified']:
            invalid.append((row['sample'],raw.get('native_error')))
            continue
        unclassified+=raw['native_unclassified_trailing_words']
        records=raw['native_full_records']
        for p,rec in enumerate(records):
            k=(rec['record_family'],rec['channel_id'])
            byfamily[rec['record_family']]+=1
            bychannel[k]+=1
            if rec['value_float32'] is not None:
                byposition[(p,*k)].append(rec['value_float32'])
        if len(records)==8 and all(x['record_family']=='0x00020000' for x in records):
            complete_peak_packets.append(row['sample'])
        if len(examples)<18:
            examples.append(dict(sample=row['sample'],payload_words=raw['native_payload_words'],
                                 native_packet_identity=raw['native_packet_identity'],
                                 records=records,
                                 trailing_words=raw['native_unclassified_trailing_words']))
    def summ(nums):
        return {'count':len(nums),'min':round(min(nums),4),
                'median':round(statistics.median(nums),4),'max':round(max(nums),4)}
    return {
        'input_rows':len(rows),
        'complete_SPI_header_and_trailer':len(invalid)==0,
        'invalid_frames_or_payloads':invalid,
        'payload_word_count_histogram':{str(k):v for k,v in sorted(bylen.items())},
        'nonempty_native_payload_frames':nonempty,
        'GR_extension_marker_present_frames':gr_count,
        'native_event_family_counts':dict(byfamily),
        'native_event_family_and_index_counts':
            {f'{a}/{b}':n for (a,b),n in sorted(bychannel.items())},
        'native_meter_family_0x00020000_complete_8record_packet_samples':complete_peak_packets,
        'native_float_values_by_order_family_channel':
            {f'position{p}:{family}/id{cid}':summ(vals)
             for (p,family,cid),vals in sorted(byposition.items())},
        'partial_native_event_trailing_words':unclassified,
        'illustrative_native_payloads':examples,
        'native_input_output_identity_calibrated':False,
        'audio_clipping_threshold_calibrated':False,
        'on_device_2bar_display_implemented':False
    }

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture',type=Path)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    rows=[json.loads(line) for line in args.capture.open() if line.strip()]
    result=analyze(rows)
    text=json.dumps(result,indent=2)+'\n'
    if args.out:args.out.write_text(text)
    print(text)

if __name__=='__main__':main()
